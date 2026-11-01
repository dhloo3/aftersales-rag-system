package org.ruoyi.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

/** Limits blocking vector and MySQL retrieval work independently of the common pool. */
@Configuration
public class KnowledgeRetrievalExecutorConfig {

    @Bean(name = "knowledgeRetrievalExecutor", destroyMethod = "shutdown")
    public ExecutorService knowledgeRetrievalExecutor(
        @Value("${knowledge.retrieval.core-pool-size:4}") int coreSize,
        @Value("${knowledge.retrieval.max-pool-size:8}") int maxSize,
        @Value("${knowledge.retrieval.queue-capacity:64}") int queueCapacity) {
        AtomicInteger counter = new AtomicInteger();
        return new ThreadPoolExecutor(coreSize, maxSize, 60, TimeUnit.SECONDS,
            new ArrayBlockingQueue<>(queueCapacity), task -> {
                Thread thread = new Thread(task, "knowledge-retrieval-" + counter.incrementAndGet());
                thread.setDaemon(true);
                return thread;
            }, new ThreadPoolExecutor.AbortPolicy());
    }
}
