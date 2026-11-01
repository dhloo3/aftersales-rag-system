package org.ruoyi.controller.knowledge;

import cn.dev33.satoken.annotation.SaCheckPermission;
import org.ruoyi.common.chat.domain.vo.chat.ChatModelVo;
import org.ruoyi.common.chat.service.chat.IChatModelService;
import org.ruoyi.domain.bo.knowledge.KnowledgeFragmentBo;
import org.ruoyi.domain.vo.knowledge.KnowledgeRetrievalVo;
import org.ruoyi.service.chat.impl.provider.DeepseekServiceImpl;
import org.ruoyi.service.knowledge.IKnowledgeFragmentService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@RestController
@RequestMapping("/system/aftersales")
public class AftersalesQaController {
    private static final Pattern ALARM_CODE = Pattern.compile("(?i)E\\d{2,}");
    private final IKnowledgeFragmentService fragments;
    private final IChatModelService models;
    private final DeepseekServiceImpl deepseek;

    public AftersalesQaController(IKnowledgeFragmentService fragments,
                                  IChatModelService models, DeepseekServiceImpl deepseek) {
        this.fragments = fragments;
        this.models = models;
        this.deepseek = deepseek;
    }

    public record AskRequest(Long knowledgeId, String question, Integer topK) { }
    public record Source(String sourceName, String docId, String fragmentId, double score, String excerpt) { }
    public record AskResponse(String status, String answer, String model, List<Source> sources) { }

    @SaCheckPermission("system:fragment:list")
    @PostMapping("/ask")
    public AskResponse ask(@RequestBody AskRequest request) {
        if (request == null || request.knowledgeId() == null || request.question() == null
                || request.question().isBlank()) {
            throw new IllegalArgumentException("知识库 ID 和问题不能为空");
        }
        int topK = request.topK() == null ? 3 : Math.max(1, Math.min(request.topK(), 5));
        KnowledgeFragmentBo query = new KnowledgeFragmentBo();
        query.setKnowledgeId(request.knowledgeId());
        query.setQuery(request.question().trim());
        query.setTopK(topK);
        query.setThreshold(0.0);
        query.setEnableHybrid(true);
        query.setHybridAlpha(0.3);
        List<KnowledgeRetrievalVo> hits = fragments.retrieval(query);
        StringBuilder evidence = new StringBuilder();
        List<Source> sources = new ArrayList<>();
        for (int i = 0; i < Math.min(topK, hits.size()); i++) {
            KnowledgeRetrievalVo hit = hits.get(i);
            evidence.append('[').append(i + 1).append("] ")
                .append(hit.getSourceName()).append("\n")
                .append(hit.getContent()).append("\n\n");
            sources.add(new Source(hit.getSourceName(), hit.getDocId(), hit.getId(),
                hit.getScore() == null ? 0.0 : hit.getScore(), hit.getContent()));
        }
        Matcher alarm = ALARM_CODE.matcher(request.question());
        while (alarm.find()) {
            String code = alarm.group().toUpperCase(Locale.ROOT);
            if (!evidence.toString().toUpperCase(Locale.ROOT).contains(code)) {
                return new AskResponse("NO_EVIDENCE",
                    "现有资料未收录 " + code + "，需联系售后工程师核实，不能推断维修步骤。",
                    "deepseek-flash", List.of());
            }
        }
        ChatModelVo model = models.selectModelByName("deepseek-flash");
        if (model == null) {
            throw new IllegalStateException("未配置 deepseek-flash 模型");
        }
        String prompt = "你是企业设备售后知识助手。只能依据下列资料回答，不能推断未写出的故障代码或维修步骤。"
            + "若资料不足，请明确说‘现有资料未收录，需联系售后工程师核实’。"
            + "每条具体结论标注资料序号，如[1]。区分通用SOP和单次历史维修记录。\n\n"
            + "资料：\n" + evidence + "问题：" + request.question();
        try {
            String answer = deepseek.buildChatModel(model).chat(prompt);
            return new AskResponse("GENERATED", answer, model.getModelName(), sources);
        } catch (RuntimeException modelFailure) {
            return new AskResponse("MODEL_UNAVAILABLE",
                "DeepSeek 当前无法生成回答，请查看返回的来源片段并联系售后工程师核实。",
                model.getModelName(), sources);
        }
    }
}
