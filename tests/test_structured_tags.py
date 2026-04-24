from app.analysis.structured_tags import extract_structured_tags


def test_extract_structured_tags_contains_useful_fields():
    tags = extract_structured_tags(
        summary="A Python RAG agent framework for building AI assistants with FastAPI and Docker.",
        reasons=["Supports multi-agent workflows", "Production-ready API service"],
        readme_content="Built with LangChain, ChromaDB, Redis and Kubernetes deployment options.",
        repo_data={"language": "Python", "topics": ["rag", "agent", "fastapi"]},
        scout_data={"community_sentiment": {"key_topics": ["RAG", "workflow"]}},
    )

    assert "Python" in tags["tech_stack"]
    assert "FastAPI" in tags["tech_stack"]
    assert "RAG Knowledge Base" in tags["use_cases"]
    assert len(tags["keywords"]) > 0


def test_extract_structured_tags_keyword_normalization_and_dedup():
    tags = extract_structured_tags(
        summary="LLMs and ChatGPT based RAG assistant with FastAPI.",
        reasons=["Large language models for retrieval workflows"],
        readme_content="This project uses OpenAI and LangChain for RAG.",
        repo_data={"language": "python", "topics": ["llm", "LLMs", "rag", "lang-chain"]},
        scout_data={"community_sentiment": {"key_topics": ["ChatGPT", "RAG"]}},
    )

    # Canonicalized tokens should be stable and deduplicated.
    assert tags["keywords"].count("LLM") <= 1
    assert "RAG" in tags["keywords"]
    assert "OpenAI" in tags["keywords"]
    assert "LangChain" in tags["keywords"]


def test_extract_structured_tags_filters_noise_and_keeps_relevant_labels():
    tags = extract_structured_tags(
        summary="Open source project framework tool platform build support",
        reasons=["Supports automation pipeline and deployment"],
        readme_content="Includes Kubernetes, Docker and CI/CD for deployment automation.",
        repo_data={"language": "TypeScript", "topics": ["workflow", "automation"]},
        scout_data={},
    )

    # Generic noise terms should not dominate keyword output.
    lowered = {k.lower() for k in tags["keywords"]}
    assert "project" not in lowered
    assert "framework" not in lowered
    assert "source" not in lowered

    assert "TypeScript" in tags["tech_stack"]
    assert "Workflow Automation" in tags["use_cases"]
