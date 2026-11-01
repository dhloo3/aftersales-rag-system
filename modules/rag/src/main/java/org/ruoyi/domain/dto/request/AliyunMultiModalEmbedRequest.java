package org.ruoyi.domain.dto.request;

import org.ruoyi.common.json.utils.JsonUtils;

import java.util.List;
import java.util.Map;

/**
 * @Author: Robust_H
 * @Date: 2025-10-1-上午10:00
 * @Description: 阿里云多模态嵌入请求
 */
public class AliyunMultiModalEmbedRequest {
    private String model;
    private Input input;
    private Map<String, Object> parameters;

    public String getModel() { return model; }
    public void setModel(String model) { this.model = model; }
    public Input getInput() { return input; }
    public void setInput(Input input) { this.input = input; }
    public Map<String, Object> getParameters() { return parameters; }
    public void setParameters(Map<String, Object> parameters) { this.parameters = parameters; }

    /**
     * 创建请求对象
     */
    public static AliyunMultiModalEmbedRequest create(String modelName, List<Map<String, Object>> contents) {
        AliyunMultiModalEmbedRequest request = new AliyunMultiModalEmbedRequest();
        request.setModel(modelName);
        Input input = new Input(contents);
        request.setInput(input);
        return request;
    }

    public static AliyunMultiModalEmbedRequest create(String modelName, List<Map<String, Object>> contents, Integer dimension) {
        AliyunMultiModalEmbedRequest request = create(modelName, contents);
        if (dimension != null && dimension > 0) {
            request.setParameters(Map.of("dimension", dimension));
        }
        return request;
    }

    /**
     * 转换为JSON字符串
     */
    public String toJson() {
        return JsonUtils.toJsonString(this);
    }

    /**
     * 表示输入数据的记录类(Record)
     * 该类用于封装一个包含多个映射关系列表的输入数据结构
     *
     * @param contents 包含多个Map的列表，每个Map中存储String类型的键和Object类型的值
     */
    public record Input(List<Map<String, Object>> contents) {
    }
}
