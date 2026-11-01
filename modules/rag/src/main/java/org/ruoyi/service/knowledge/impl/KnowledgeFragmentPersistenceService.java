package org.ruoyi.service.knowledge.impl;

import com.baomidou.mybatisplus.core.toolkit.Wrappers;
import lombok.RequiredArgsConstructor;
import org.ruoyi.domain.entity.knowledge.KnowledgeAttach;
import org.ruoyi.domain.entity.knowledge.KnowledgeFragment;
import org.ruoyi.enums.KnowledgeAttachStatus;
import org.ruoyi.mapper.knowledge.KnowledgeAttachMapper;
import org.ruoyi.mapper.knowledge.KnowledgeFragmentMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/** Atomically replaces MySQL fragments and marks the attachment complete. */
@Service
@RequiredArgsConstructor
public class KnowledgeFragmentPersistenceService {

    private final KnowledgeFragmentMapper fragmentMapper;
    private final KnowledgeAttachMapper attachMapper;

    @Transactional(rollbackFor = Exception.class)
    public void replace(String docId, List<KnowledgeFragment> fragments, KnowledgeAttach attachment) {
        fragmentMapper.delete(Wrappers.<KnowledgeFragment>lambdaQuery()
            .eq(KnowledgeFragment::getDocId, docId));
        fragmentMapper.insertBatch(fragments);
        attachment.setStatus(KnowledgeAttachStatus.COMPLETED.getCode());
        attachMapper.updateById(attachment);
    }
}
