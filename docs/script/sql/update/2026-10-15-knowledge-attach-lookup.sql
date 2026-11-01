-- Run once on existing MySQL installations before deploying keyword source lookup.
ALTER TABLE `knowledge_attach`
    ADD INDEX `idx_knowledge_doc_id` (`knowledge_id`, `doc_id`);
