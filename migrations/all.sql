CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. SOURCE
CREATE TABLE IF NOT EXISTS source (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset JSONB,
    title TEXT,
    topics TEXT[],                -- array<string>
    full_text TEXT,
    created TIMESTAMPTZ DEFAULT now(),
    updated TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_insight (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES source(id) ON DELETE CASCADE,
    insight_type TEXT NOT NULL,
    content TEXT NOT NULL
);

-- NOTEBOOK
CREATE TABLE IF NOT EXISTS notebook (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT,
    description TEXT,
    archived BOOLEAN DEFAULT FALSE,
    created TIMESTAMPTZ DEFAULT now(),
    updated TIMESTAMPTZ DEFAULT now()
);

-- RELATION source -> notebook
CREATE TABLE IF NOT EXISTS reference (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES source(id) ON DELETE CASCADE,
    notebook_id UUID REFERENCES notebook(id) ON DELETE CASCADE,
    UNIQUE (source_id, notebook_id)
);

-- CHAT_SESSION
CREATE TABLE IF NOT EXISTS chat_session (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payload JSONB   -- schema-less, so flexible JSON
);

-- RELATION chat_session -> notebook
CREATE TABLE IF NOT EXISTS refers_to (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id UUID REFERENCES chat_session(id) ON DELETE CASCADE,
    notebook_id UUID REFERENCES notebook(id) ON DELETE CASCADE,
    UNIQUE (chat_session_id, notebook_id)
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

-- Insert default transformations
INSERT INTO transformation (name, title, description, prompt, apply_default)
VALUES
(
    'Analyze Paper',
    'Paper Analysis',
    'Analyses a technical/scientific paper',
    '# IDENTITY and PURPOSE

You are an insightful and analytical reader of academic papers, extracting the key components, significance, and broader implications. ...
(Output omitted here for brevity – keep full prompt)',
    FALSE
),
(
    'Key Insights',
    'Key Insights',
    'Extracts important insights and actionable items',
    '# IDENTITY and PURPOSE

You extract surprising, powerful, and interesting insights from text content. ...
(Output omitted here for brevity – keep full prompt)',
    FALSE
),
(
    'Dense Summary',
    'Dense Summary',
    'Creates a rich, deep summary of the content',
    '# MISSION
You are a Sparse Priming Representation (SPR) writer. ...
(Output omitted here for brevity – keep full prompt)',
    TRUE
),
(
    'Reflections',
    'Reflection Questions',
    'Generates reflection questions from the document to help explore it further',
    '# IDENTITY and PURPOSE

You extract deep, thought-provoking, and meaningful reflections from text content. ...
(Output omitted here for brevity – keep full prompt)',
    FALSE
),
(
    'Table of Contents',
    'Table of Contents',
    'Describes the different topics of the document',
    '# SYSTEM ROLE
You are a content analysis assistant ...
(Output omitted here for brevity – keep full prompt)',
    FALSE
),
(
    'Simple Summary',
    'Simple Summary',
    'Generates a small summary of the content',
    '# SYSTEM ROLE
You are a content summarization assistant ...
(Output omitted here for brevity – keep full prompt)',
    FALSE
);
