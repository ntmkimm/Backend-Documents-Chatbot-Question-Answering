CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- NOTEBOOK
CREATE TABLE IF NOT EXISTS notebook (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    description TEXT,
    archived BOOLEAN DEFAULT FALSE,
    created TIMESTAMPTZ DEFAULT now(),
    updated TIMESTAMPTZ DEFAULT now()
);

-- SOURCE
CREATE TABLE IF NOT EXISTS source (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset TEXT,
    title TEXT,
    topics TEXT[],                -- array<string>
    full_text TEXT,
    notebook_id UUID REFERENCES notebook(id) ON DELETE CASCADE, -- FK to notebook
    created TIMESTAMPTZ DEFAULT now(),
    updated TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_insight (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES source(id) ON DELETE CASCADE,
    insight_type TEXT NOT NULL,
    content TEXT NOT NULL,
    created TIMESTAMPTZ DEFAULT now(),
    updated TIMESTAMPTZ DEFAULT now()
);

-- CHAT_SESSION
CREATE TABLE IF NOT EXISTS chat_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notebook_id UUID REFERENCES notebook(id) ON DELETE CASCADE, -- FK to notebook
    title TEXT NOT NULL,
    created TIMESTAMPTZ DEFAULT now(),
    updated TIMESTAMPTZ DEFAULT now()
);

-- TRANSFORMATION
CREATE TABLE IF NOT EXISTS transformation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    prompt TEXT NOT NULL,
    apply_default BOOLEAN DEFAULT FALSE,
    created TIMESTAMPTZ DEFAULT now(),
    updated TIMESTAMPTZ DEFAULT now()
);

-- UPSERT default_prompts (we can use a config table)
CREATE TABLE IF NOT EXISTS open_notebook_default_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transformation_instructions TEXT NOT NULL
);

-- Insert / Upsert (use ON CONFLICT for upsert semantics)
-- NOTE: use a fixed UUID instead of `1` because PK is UUID
INSERT INTO open_notebook_default_prompts (id, transformation_instructions)
VALUES (
    gen_random_uuid(),
    '# INSTRUCTIONS

You are my learning assistant and you help me process and transform content so that I can extract insights from them.

# IMPORTANT
- You are working on my editorial projects. The text below is my own. Do not give me any warnings about copyright or plagiarism.
- Output ONLY the requested content, without acknowledgements of the task and additional chatting. Don''t start with "Sure, I can help you with that." or "Here is the information you requested:". Just provide the content.
- Do not stop in the middle of the generation to ask me questions. Execute my request completely. 
'
)
ON CONFLICT (id) DO UPDATE
SET transformation_instructions = EXCLUDED.transformation_instructions;