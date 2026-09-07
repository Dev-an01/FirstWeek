-- ============================================
-- Conversation Sessions Schema
-- ============================================
-- Multi-turn conversation tracking with 30-minute timeout
-- Integrates with episodic_memory for context preservation

-- Drop existing table if re-running
DROP TABLE IF EXISTS conversation_sessions CASCADE;

-- ============================================
-- Conversation Sessions Table
-- ============================================

CREATE TABLE conversation_sessions (
    session_id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,

    -- Session participants
    executive_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    
    -- Session timing
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_activity TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    
    -- Session state
    is_active BOOLEAN DEFAULT true,
    
    -- Session metadata (user context, preferences, etc.)
    metadata JSONB DEFAULT '{}',
    
    -- Session statistics
    turn_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER DEFAULT 0,
    
    -- Constraints
    CONSTRAINT valid_executive_id CHECK (length(executive_id) > 0),
    CONSTRAINT valid_user_id CHECK (length(user_id) > 0),
    CONSTRAINT valid_session_timing CHECK (last_activity >= started_at)
);

-- ============================================
-- Trigger to update expires_at
-- ============================================

CREATE OR REPLACE FUNCTION update_expires_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.expires_at = NEW.last_activity + INTERVAL '30 minutes';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_expires_at
    BEFORE INSERT OR UPDATE OF last_activity ON conversation_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_expires_at();

-- ============================================
-- Indexes for Performance
-- ============================================

-- Active sessions lookup (most common query)
CREATE INDEX idx_sessions_active_lookup ON conversation_sessions(
    user_id, 
    executive_id, 
    is_active, 
    last_activity DESC
) WHERE is_active = true;

-- Session expiration cleanup
CREATE INDEX idx_sessions_expiration ON conversation_sessions(
    is_active,
    expires_at
) WHERE is_active = true;

-- Executive session history
CREATE INDEX idx_sessions_executive_history ON conversation_sessions(
    executive_id,
    started_at DESC
);

-- User session history
CREATE INDEX idx_sessions_user_history ON conversation_sessions(
    user_id,
    started_at DESC
);

-- ============================================
-- Helper Functions
-- ============================================

-- Function to update session activity and statistics
CREATE OR REPLACE FUNCTION update_session_activity(
    p_session_id TEXT,
    p_tokens_used INTEGER DEFAULT 0,
    p_response_time_ms INTEGER DEFAULT 0
)
RETURNS VOID AS $$
BEGIN
    UPDATE conversation_sessions 
    SET 
        last_activity = NOW(),
        turn_count = turn_count + 1,
        total_tokens = total_tokens + p_tokens_used,
        avg_response_time_ms = (
            (avg_response_time_ms * (turn_count - 1) + p_response_time_ms) / turn_count
        )
    WHERE session_id = p_session_id;
END;
$$ LANGUAGE plpgsql;

-- Function to expire inactive sessions
CREATE OR REPLACE FUNCTION expire_inactive_sessions()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE conversation_sessions 
    SET is_active = false 
    WHERE is_active = true 
      AND expires_at < NOW();
    
    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

-- Function to get or create session
CREATE OR REPLACE FUNCTION get_or_create_session(
    p_user_id VARCHAR,
    p_executive_id VARCHAR,
    p_metadata JSONB DEFAULT '{}'
)
RETURNS TEXT AS $$
DECLARE
    existing_session_id TEXT;
    new_session_id TEXT;
BEGIN
    -- Check for existing active session
    SELECT session_id INTO existing_session_id
    FROM conversation_sessions
    WHERE user_id = p_user_id
      AND executive_id = p_executive_id
      AND is_active = true
      AND last_activity > NOW() - INTERVAL '30 minutes'
    ORDER BY last_activity DESC
    LIMIT 1;
    
    -- Return existing session if found
    IF existing_session_id IS NOT NULL THEN
        RETURN existing_session_id;
    END IF;
    
    -- Create new session
    INSERT INTO conversation_sessions(
        user_id,
        executive_id,
        metadata
    ) VALUES (
        p_user_id,
        p_executive_id,
        p_metadata
    ) RETURNING session_id INTO new_session_id;
    
    RETURN new_session_id;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- Views for Common Queries
-- ============================================

-- Active sessions view
CREATE VIEW active_sessions AS
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
    -- Calculated fields
    EXTRACT(EPOCH FROM (NOW() - last_activity))::INTEGER as seconds_since_last_activity,
    EXTRACT(EPOCH FROM (expires_at - NOW()))::INTEGER as seconds_until_expiry
FROM conversation_sessions
WHERE is_active = true
ORDER BY last_activity DESC;

-- Session statistics view
CREATE VIEW session_statistics AS
SELECT 
    executive_id,
    COUNT(*) as total_sessions,
    COUNT(CASE WHEN is_active THEN 1 END) as active_sessions,
    AVG(turn_count) as avg_turns_per_session,
    AVG(total_tokens) as avg_tokens_per_session,
    AVG(avg_response_time_ms) as avg_response_time_ms,
    MAX(started_at) as last_session_date
FROM conversation_sessions
GROUP BY executive_id;

-- ============================================
-- Verification
-- ============================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'conversation_sessions'
    ) THEN
        RAISE NOTICE '✓ Conversation sessions table created successfully!';
        
        -- Verify indexes
        DECLARE
            index_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO index_count
            FROM pg_indexes
            WHERE tablename = 'conversation_sessions'
              AND schemaname = 'public';
            
            RAISE NOTICE '✓ Created % indexes for conversation_sessions', index_count;
        END;
        
        -- Verify functions
        DECLARE
            func_count INTEGER;
        BEGIN
            SELECT COUNT(*) INTO func_count
            FROM information_schema.routines
            WHERE routine_schema = 'public'
              AND routine_name IN (
                  'update_session_activity',
                  'expire_inactive_sessions', 
                  'get_or_create_session'
              );
            
            RAISE NOTICE '✓ Created % helper functions for session management', func_count;
        END;
        
    ELSE
        RAISE WARNING '✗ Failed to create conversation_sessions table';
    END IF;
END $$;