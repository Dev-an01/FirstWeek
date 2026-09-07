-- ============================================
-- Conversation Engine Schema Extension
-- ============================================
-- Extends the existing conversation_sessions table with
-- additional columns for the Conversation Engine.
--
-- Prerequisites:
-- - conversation_sessions table must exist
-- - Run config/conversation_sessions_schema.sql first
--
-- Safe to run multiple times (idempotent)
-- ============================================

-- ============================================
-- Verify Base Table Exists
-- ============================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_tables
        WHERE schemaname = 'public'
        AND tablename = 'conversation_sessions'
    ) THEN
        RAISE EXCEPTION 'Base table conversation_sessions does not exist. Run conversation_sessions_schema.sql first.';
    END IF;
END $$;

-- ============================================
-- Add New Columns
-- ============================================

-- Conversation state (full JSONB for ConversationState)
ALTER TABLE conversation_sessions
ADD COLUMN IF NOT EXISTS conversation_state JSONB DEFAULT '{}';

-- Current topic for quick filtering
ALTER TABLE conversation_sessions
ADD COLUMN IF NOT EXISTS current_topic VARCHAR(255);

-- Current detected emotion
ALTER TABLE conversation_sessions
ADD COLUMN IF NOT EXISTS current_emotion VARCHAR(50) DEFAULT 'neutral';

-- Facts already provided (to avoid repetition)
ALTER TABLE conversation_sessions
ADD COLUMN IF NOT EXISTS facts_provided JSONB DEFAULT '[]';

-- Sources already cited
ALTER TABLE conversation_sessions
ADD COLUMN IF NOT EXISTS sources_cited JSONB DEFAULT '[]';

-- Emotional trend (stable, improving, declining)
ALTER TABLE conversation_sessions
ADD COLUMN IF NOT EXISTS emotional_trend VARCHAR(20) DEFAULT 'stable';

-- Mode used (stateless, session, memory_aware)
ALTER TABLE conversation_sessions
ADD COLUMN IF NOT EXISTS conversation_mode VARCHAR(20) DEFAULT 'session';

-- ============================================
-- Add Indexes for New Columns
-- ============================================

-- GIN index for JSONB conversation_state queries
CREATE INDEX IF NOT EXISTS idx_sessions_conversation_state
ON conversation_sessions USING GIN (conversation_state);

-- Index for topic-based filtering
CREATE INDEX IF NOT EXISTS idx_sessions_current_topic
ON conversation_sessions (current_topic)
WHERE current_topic IS NOT NULL;

-- Index for emotion-based queries
CREATE INDEX IF NOT EXISTS idx_sessions_current_emotion
ON conversation_sessions (current_emotion);

-- Index for mode-based filtering
CREATE INDEX IF NOT EXISTS idx_sessions_conversation_mode
ON conversation_sessions (conversation_mode);

-- GIN index for facts_provided array queries
CREATE INDEX IF NOT EXISTS idx_sessions_facts_provided
ON conversation_sessions USING GIN (facts_provided);

-- ============================================
-- Helper Functions
-- ============================================

-- Function to update conversation state
CREATE OR REPLACE FUNCTION update_conversation_state(
    p_session_id TEXT,
    p_conversation_state JSONB,
    p_current_topic VARCHAR DEFAULT NULL,
    p_current_emotion VARCHAR DEFAULT 'neutral',
    p_emotional_trend VARCHAR DEFAULT 'stable'
)
RETURNS VOID AS $$
BEGIN
    UPDATE conversation_sessions
    SET
        conversation_state = p_conversation_state,
        current_topic = COALESCE(p_current_topic, current_topic),
        current_emotion = p_current_emotion,
        emotional_trend = p_emotional_trend,
        last_activity = NOW()
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- Function to add facts to session
CREATE OR REPLACE FUNCTION add_session_facts(
    p_session_id TEXT,
    p_new_facts JSONB
)
RETURNS VOID AS $$
BEGIN
    UPDATE conversation_sessions
    SET
        facts_provided = (
            SELECT jsonb_agg(DISTINCT elem)
            FROM (
                SELECT jsonb_array_elements(facts_provided) AS elem
                UNION ALL
                SELECT jsonb_array_elements(p_new_facts) AS elem
            ) combined
            -- Limit to 50 most recent facts
            LIMIT 50
        ),
        last_activity = NOW()
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- Function to add cited sources
CREATE OR REPLACE FUNCTION add_session_sources(
    p_session_id TEXT,
    p_new_sources JSONB
)
RETURNS VOID AS $$
BEGIN
    UPDATE conversation_sessions
    SET
        sources_cited = (
            SELECT jsonb_agg(DISTINCT elem)
            FROM (
                SELECT jsonb_array_elements(sources_cited) AS elem
                UNION ALL
                SELECT jsonb_array_elements(p_new_sources) AS elem
            ) combined
        ),
        last_activity = NOW()
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get session with conversation state
CREATE OR REPLACE FUNCTION get_session_with_state(p_session_id TEXT)
RETURNS TABLE (
    session_id TEXT,
    executive_id VARCHAR,
    user_id VARCHAR,
    conversation_state JSONB,
    current_topic VARCHAR,
    current_emotion VARCHAR,
    emotional_trend VARCHAR,
    conversation_mode VARCHAR,
    facts_provided JSONB,
    sources_cited JSONB,
    turn_count INTEGER,
    started_at TIMESTAMPTZ,
    last_activity TIMESTAMPTZ,
    seconds_since_activity INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        s.session_id,
        s.executive_id,
        s.user_id,
        s.conversation_state,
        s.current_topic,
        s.current_emotion,
        s.emotional_trend,
        s.conversation_mode,
        s.facts_provided,
        s.sources_cited,
        s.turn_count,
        s.started_at,
        s.last_activity,
        EXTRACT(EPOCH FROM (NOW() - s.last_activity))::INTEGER
    FROM conversation_sessions s
    WHERE s.session_id = p_session_id
      AND s.is_active = true;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Update Views
-- ============================================

-- Drop and recreate active_sessions view with new columns
DROP VIEW IF EXISTS active_sessions_extended;

CREATE VIEW active_sessions_extended AS
SELECT
    session_id,
    user_id,
    executive_id,
    started_at,
    last_activity,
    expires_at,
    turn_count,
    total_tokens,
    avg_response_time_ms,
    metadata,
    conversation_state,
    current_topic,
    current_emotion,
    emotional_trend,
    conversation_mode,
    facts_provided,
    sources_cited,
    -- Calculated fields
    EXTRACT(EPOCH FROM (NOW() - last_activity))::INTEGER as seconds_since_last_activity,
    EXTRACT(EPOCH FROM (expires_at - NOW()))::INTEGER as seconds_until_expiry,
    jsonb_array_length(facts_provided) as facts_count,
    jsonb_array_length(sources_cited) as sources_count
FROM conversation_sessions
WHERE is_active = true
ORDER BY last_activity DESC;

-- ============================================
-- Verification
-- ============================================

DO $$
DECLARE
    column_count INTEGER;
    function_count INTEGER;
BEGIN
    -- Count new columns
    SELECT COUNT(*) INTO column_count
    FROM information_schema.columns
    WHERE table_name = 'conversation_sessions'
      AND column_name IN (
          'conversation_state',
          'current_topic',
          'current_emotion',
          'facts_provided',
          'sources_cited',
          'emotional_trend',
          'conversation_mode'
      );

    -- Count new functions
    SELECT COUNT(*) INTO function_count
    FROM information_schema.routines
    WHERE routine_schema = 'public'
      AND routine_name IN (
          'update_conversation_state',
          'add_session_facts',
          'add_session_sources',
          'get_session_with_state'
      );

    RAISE NOTICE '✓ Conversation Engine schema extension complete:';
    RAISE NOTICE '  - Added % new columns to conversation_sessions', column_count;
    RAISE NOTICE '  - Created % helper functions', function_count;
    RAISE NOTICE '  - Created active_sessions_extended view';
END $$;

-- ============================================
-- Sample Queries (for reference)
-- ============================================

-- Get session with full conversation state:
-- SELECT * FROM get_session_with_state('your-session-id-here');

-- Update conversation state after a turn:
-- SELECT update_conversation_state(
--     'session-id',
--     '{"turns": [...], "current_topic": "budget"}',
--     'budget',
--     'neutral',
--     'stable'
-- );

-- Add facts to avoid repetition:
-- SELECT add_session_facts('session-id', '["MegaCorp NPS is 72", "45-day deadline"]');

-- Get extended session info:
-- SELECT * FROM active_sessions_extended WHERE executive_id = 'exec_001_test';
