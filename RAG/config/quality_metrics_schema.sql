-- Quality Metrics Table
-- Stores quality evaluation results for each response

CREATE TABLE IF NOT EXISTS quality_metrics (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(255) NOT NULL,
    executive_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    query_text TEXT,
    response_text TEXT,

    -- Quality scores
    citation_coverage FLOAT,  -- 0-100
    factual_grounding_rate FLOAT,  -- 0-100
    total_claims INTEGER,
    grounded_claims INTEGER,
    decision_fidelity_score FLOAT,  -- 0-1

    -- Metadata
    model VARCHAR(255),
    path VARCHAR(50),  -- fast/standard/agentic
    sources_count INTEGER,
    citations_count INTEGER,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for quality_metrics
CREATE INDEX IF NOT EXISTS idx_qm_request_id ON quality_metrics(request_id);
CREATE INDEX IF NOT EXISTS idx_qm_executive_id ON quality_metrics(executive_id);
CREATE INDEX IF NOT EXISTS idx_qm_created_at ON quality_metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_qm_path ON quality_metrics(path);

-- User Feedback Table
-- Stores thumbs up/down and user comments

CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    request_id VARCHAR(255) NOT NULL,
    executive_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),

    -- Feedback
    feedback_type VARCHAR(50) NOT NULL,  -- thumbs_up, thumbs_down, comment
    rating INTEGER,  -- 1-5 stars (optional)
    comment TEXT,

    -- Context
    query_text TEXT,
    response_text TEXT,
    path VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for user_feedback
CREATE INDEX IF NOT EXISTS idx_uf_request_id ON user_feedback(request_id);
CREATE INDEX IF NOT EXISTS idx_uf_executive_id ON user_feedback(executive_id);
CREATE INDEX IF NOT EXISTS idx_uf_feedback_type ON user_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_uf_created_at ON user_feedback(created_at);

-- Business Metrics Table
-- Stores aggregated daily business metrics

CREATE TABLE IF NOT EXISTS business_metrics (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,

    -- User engagement
    daily_active_users INTEGER DEFAULT 0,
    total_queries INTEGER DEFAULT 0,
    unique_users INTEGER DEFAULT 0,

    -- Query distribution
    fast_path_queries INTEGER DEFAULT 0,
    standard_path_queries INTEGER DEFAULT 0,
    agentic_path_queries INTEGER DEFAULT 0,

    -- Performance
    avg_response_time_seconds FLOAT,
    p95_response_time_seconds FLOAT,
    error_count INTEGER DEFAULT 0,
    error_rate FLOAT,

    -- Quality
    avg_citation_coverage FLOAT,
    avg_factual_grounding FLOAT,
    avg_decision_fidelity FLOAT,

    -- User satisfaction
    thumbs_up_count INTEGER DEFAULT 0,
    thumbs_down_count INTEGER DEFAULT 0,
    satisfaction_rate FLOAT,

    -- Cost
    total_tokens INTEGER DEFAULT 0,
    total_cost_usd FLOAT DEFAULT 0.0,
    avg_cost_per_query FLOAT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index for business_metrics
CREATE INDEX IF NOT EXISTS idx_bm_date ON business_metrics(date);

-- User Activity Tracking
-- Tracks user sessions for DAU/MAU/retention calculations

CREATE TABLE IF NOT EXISTS user_activity (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    executive_id VARCHAR(255),
    session_id VARCHAR(255),

    -- Activity
    activity_type VARCHAR(50) NOT NULL,  -- query, feedback, login
    activity_date DATE NOT NULL,

    -- Context
    path VARCHAR(50),
    success BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for user_activity
CREATE INDEX IF NOT EXISTS idx_ua_user_id ON user_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_ua_activity_date ON user_activity(activity_date);
CREATE INDEX IF NOT EXISTS idx_ua_activity_type ON user_activity(activity_type);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ua_user_date ON user_activity(user_id, activity_date);

-- Function to update business metrics daily
CREATE OR REPLACE FUNCTION update_business_metrics(target_date DATE)
RETURNS VOID AS $$
BEGIN
    INSERT INTO business_metrics (
        date,
        daily_active_users,
        total_queries,
        unique_users,
        fast_path_queries,
        standard_path_queries,
        agentic_path_queries,
        avg_citation_coverage,
        avg_factual_grounding,
        avg_decision_fidelity,
        thumbs_up_count,
        thumbs_down_count,
        satisfaction_rate,
        updated_at
    )
    SELECT
        target_date,
        COUNT(DISTINCT user_id) as daily_active_users,
        COUNT(*) as total_queries,
        COUNT(DISTINCT user_id) as unique_users,
        SUM(CASE WHEN path = 'fast' THEN 1 ELSE 0 END) as fast_path_queries,
        SUM(CASE WHEN path = 'standard' THEN 1 ELSE 0 END) as standard_path_queries,
        SUM(CASE WHEN path = 'agentic' THEN 1 ELSE 0 END) as agentic_path_queries,
        AVG(citation_coverage) as avg_citation_coverage,
        AVG(factual_grounding_rate) as avg_factual_grounding,
        AVG(decision_fidelity_score) as avg_decision_fidelity,
        (SELECT COUNT(*) FROM user_feedback
         WHERE DATE(created_at) = target_date AND feedback_type = 'thumbs_up') as thumbs_up_count,
        (SELECT COUNT(*) FROM user_feedback
         WHERE DATE(created_at) = target_date AND feedback_type = 'thumbs_down') as thumbs_down_count,
        (SELECT
            CASE WHEN (thumbs_up + thumbs_down) > 0
            THEN (thumbs_up::FLOAT / (thumbs_up + thumbs_down)) * 100
            ELSE NULL END
         FROM (
            SELECT
                COUNT(*) FILTER (WHERE feedback_type = 'thumbs_up') as thumbs_up,
                COUNT(*) FILTER (WHERE feedback_type = 'thumbs_down') as thumbs_down
            FROM user_feedback
            WHERE DATE(created_at) = target_date
         ) fb
        ) as satisfaction_rate,
        CURRENT_TIMESTAMP
    FROM quality_metrics
    WHERE DATE(created_at) = target_date
    ON CONFLICT (date)
    DO UPDATE SET
        daily_active_users = EXCLUDED.daily_active_users,
        total_queries = EXCLUDED.total_queries,
        unique_users = EXCLUDED.unique_users,
        fast_path_queries = EXCLUDED.fast_path_queries,
        standard_path_queries = EXCLUDED.standard_path_queries,
        agentic_path_queries = EXCLUDED.agentic_path_queries,
        avg_citation_coverage = EXCLUDED.avg_citation_coverage,
        avg_factual_grounding = EXCLUDED.avg_factual_grounding,
        avg_decision_fidelity = EXCLUDED.avg_decision_fidelity,
        thumbs_up_count = EXCLUDED.thumbs_up_count,
        thumbs_down_count = EXCLUDED.thumbs_down_count,
        satisfaction_rate = EXCLUDED.satisfaction_rate,
        updated_at = CURRENT_TIMESTAMP;
END;
$$ LANGUAGE plpgsql;

-- Comments for documentation
COMMENT ON TABLE quality_metrics IS 'Stores quality evaluation results for each AI response';
COMMENT ON TABLE user_feedback IS 'Stores user feedback (thumbs up/down, comments)';
COMMENT ON TABLE business_metrics IS 'Daily aggregated business metrics for dashboards';
COMMENT ON TABLE user_activity IS 'Tracks user activity for retention and engagement metrics';
COMMENT ON FUNCTION update_business_metrics(DATE) IS 'Updates business_metrics table for a given date';
