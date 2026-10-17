"""Verify the installed LangChain API surface before implementing chains."""
from importlib import import_module
from importlib.metadata import version
import inspect

IMPORTS = {
    "langchain_core.globals": ["set_llm_cache"],
    "langchain_community.cache": ["SQLiteCache"],
    "langchain_core.runnables": ["RunnableLambda", "RunnablePassthrough"],
    "langchain_core.prompts": ["ChatPromptTemplate"],
    "langchain_core.messages": ["HumanMessage"],
    "langchain_core.documents": ["Document"],
    "langchain_core.retrievers": ["BaseRetriever"],
    "langchain_core.exceptions": ["OutputParserException"],
    "langchain_text_splitters": ["RecursiveCharacterTextSplitter", "MarkdownHeaderTextSplitter"],
    "langchain_chroma": ["Chroma"],
    "langchain_huggingface": ["HuggingFaceEmbeddings"],
    "langchain_google_genai": ["ChatGoogleGenerativeAI"],
}


def main() -> None:
    """Print versions and confirm the exact imports used by the application."""
    for name in ("langchain-core", "langchain-text-splitters", "langchain-chroma", "langchain-huggingface", "langchain-google-genai", "langchain-community"):
        print(f"{name}=={version(name)}", flush=True)
    for module, names in IMPORTS.items():
        loaded = import_module(module)
        for name in names:
            assert getattr(loaded, name) is not None
            print(f"PASS {module}.{name}", flush=True)
    from langchain_google_genai import ChatGoogleGenerativeAI
    print("Structured output:", inspect.signature(ChatGoogleGenerativeAI.with_structured_output), flush=True)
    print("Model fields:", ", ".join(name for name in ChatGoogleGenerativeAI.model_fields if any(x in name for x in ("api_key", "model", "retries", "timeout"))), flush=True)


if __name__ == "__main__":
    main()
