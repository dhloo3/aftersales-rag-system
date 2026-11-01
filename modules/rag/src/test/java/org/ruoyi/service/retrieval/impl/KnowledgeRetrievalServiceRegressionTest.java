package org.ruoyi.service.retrieval.impl;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.ruoyi.common.trace.config.TraceProperties;
import org.ruoyi.common.trace.service.TraceRecordService;
import org.ruoyi.domain.bo.vector.QueryVectorBo;
import org.ruoyi.domain.vo.knowledge.KnowledgeRetrievalVo;
import org.ruoyi.factory.RerankModelFactory;
import org.ruoyi.mapper.knowledge.KnowledgeFragmentMapper;
import org.ruoyi.service.vector.VectorStoreService;

import java.lang.reflect.Method;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

@Tag("dev")
class KnowledgeRetrievalServiceRegressionTest {

    @Test
    void rrfMergesSameStableIdAndKeepsDistinctItems() throws Exception {
        KnowledgeRetrievalServiceImpl service = new KnowledgeRetrievalServiceImpl(
            mock(VectorStoreService.class), mock(RerankModelFactory.class), mock(KnowledgeFragmentMapper.class),
            mock(TraceRecordService.class), new TraceProperties(), mock(ExecutorService.class));
        KnowledgeRetrievalVo vectorA = item("fid-a", "A", 0.9);
        KnowledgeRetrievalVo vectorB = item("fid-b", "B", 0.8);
        KnowledgeRetrievalVo keywordA = item("fid-a", "A", 10.0);
        KnowledgeRetrievalVo keywordC = item("fid-c", "C", 10.0);

        Method method = KnowledgeRetrievalServiceImpl.class.getDeclaredMethod(
            "calculateRRF", List.class, List.class, double.class);
        method.setAccessible(true);
        @SuppressWarnings("unchecked")
        List<KnowledgeRetrievalVo> result = (List<KnowledgeRetrievalVo>) method.invoke(
            service, List.of(vectorA, vectorB), List.of(keywordA, keywordC), 0.5);

        assertEquals(3, result.size());
        assertEquals("fid-a", result.get(0).getId(), "an item present in both rankings must win");
        assertEquals(3, result.stream().map(KnowledgeRetrievalVo::getId).distinct().count());
    }

    @Test
    void rerankThresholdDoesNotLeakIntoNonRerankRetrieval() {
        VectorStoreService vectorStore = mock(VectorStoreService.class);
        when(vectorStore.search(org.mockito.ArgumentMatchers.any())).thenReturn(List.of(item("fid-a", "A", 0.75)));
        KnowledgeRetrievalServiceImpl service = new KnowledgeRetrievalServiceImpl(
            vectorStore, mock(RerankModelFactory.class), mock(KnowledgeFragmentMapper.class),
            mock(TraceRecordService.class), new TraceProperties(), mock(ExecutorService.class));
        QueryVectorBo query = new QueryVectorBo();
        query.setKid("1");
        query.setQuery("test");
        query.setMaxResults(5);
        query.setEnableHybrid(false);
        query.setEnableRerank(false);
        query.setSimilarityThreshold(0.5);
        query.setRerankScoreThreshold(0.9);

        List<KnowledgeRetrievalVo> result = service.retrieve(query);

        assertEquals(1, result.size());
        assertEquals("fid-a", result.get(0).getId());
    }

    @Test
    void hybridRetrievalKeepsKeywordResultsWhenVectorBranchTimesOut() throws Exception {
        VectorStoreService vectorStore = mock(VectorStoreService.class);
        when(vectorStore.search(org.mockito.ArgumentMatchers.any())).thenAnswer(invocation -> {
            Thread.sleep(500);
            return List.of(item("vector", "vector", 0.9));
        });
        KnowledgeFragmentMapper fragmentMapper = mock(KnowledgeFragmentMapper.class);
        org.ruoyi.domain.vo.knowledge.KnowledgeFragmentVo fragment =
            new org.ruoyi.domain.vo.knowledge.KnowledgeFragmentVo();
        fragment.setId(1L);
        fragment.setFid("keyword");
        fragment.setContent("E17");
        fragment.setSourceName("AX-200-故障排查SOP.md");
        when(fragmentMapper.searchByKeyword(1L, "E17", 5)).thenReturn(List.of(fragment));
        ExecutorService executor = Executors.newFixedThreadPool(2);
        try {
            KnowledgeRetrievalServiceImpl service = new KnowledgeRetrievalServiceImpl(
                vectorStore, mock(RerankModelFactory.class), fragmentMapper,
                mock(TraceRecordService.class), new TraceProperties(), executor);
            var timeout = KnowledgeRetrievalServiceImpl.class.getDeclaredField("retrievalTimeoutMs");
            timeout.setAccessible(true);
            timeout.setLong(service, 100);
            QueryVectorBo query = new QueryVectorBo();
            query.setKid("1");
            query.setQuery("E17");
            query.setMaxResults(5);
            query.setEnableHybrid(true);
            query.setHybridAlpha(0.5);
            long started = System.nanoTime();

            List<KnowledgeRetrievalVo> result = service.retrieve(query);

            assertEquals(1, result.size());
            assertEquals("keyword", result.get(0).getId());
            assertEquals("AX-200-故障排查SOP.md", result.get(0).getSourceName());
            assertTrue(TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started) < 400);
        } finally {
            executor.shutdownNow();
        }
    }

    private static KnowledgeRetrievalVo item(String id, String content, double score) {
        return KnowledgeRetrievalVo.builder().id(id).content(content).score(score).build();
    }
}
