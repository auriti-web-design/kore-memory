"""
Using Kore Memory as a LangChain memory backend.

Demonstrates how to:
- Create a KoreLangChainMemory instance
- Use it to save and retrieve conversation context
- Integrate it with LangChain chains (conceptual example)

Prerequisites:
    pip install kore-memory langchain-core
    kore  # start the server on localhost:8765

Note: This example shows the KoreLangChainMemory API directly.
For a full LangChain chain integration, you would also need an LLM
provider (e.g., langchain-openai).
"""

from kore_memory.integrations.langchain import KoreLangChainMemory


def main() -> None:
    # -- Create the memory backend --------------------------------------------
    # KoreLangChainMemory wraps a KoreClient and implements LangChain's
    # BaseMemory interface, so it can be used with any LangChain chain.
    memory = KoreLangChainMemory(
        base_url="http://localhost:8765",
        agent_id="langchain-agent",
        # Number of memories to retrieve per query
        k=5,
        # Use semantic search for better relevance (requires sentence-transformers)
        semantic=True,
        # Category for saved conversation turns
        category="general",
        # Let the server auto-score importance based on content
        auto_importance=True,
    )

    # -- Save conversation context --------------------------------------------
    # save_context() stores a conversation turn (input + output) as a memory.
    # In a real LangChain chain, this is called automatically after each step.
    memory.save_context(
        inputs={"input": "What is Kore Memory?"},
        outputs={"output": "Kore Memory is a persistent memory layer for AI agents."},
    )
    print("Saved conversation turn 1.")

    memory.save_context(
        inputs={"input": "Does it require an LLM?"},
        outputs={"output": "No, Kore runs fully offline with no LLM calls."},
    )
    print("Saved conversation turn 2.")

    memory.save_context(
        inputs={"input": "How does it handle forgetting?"},
        outputs={"output": "It uses the Ebbinghaus forgetting curve to decay old memories."},
    )
    print("Saved conversation turn 3.")

    # -- Load memory variables ------------------------------------------------
    # load_memory_variables() retrieves relevant past memories based on
    # the current input. This is called automatically by LangChain chains
    # to inject context into the prompt.
    context = memory.load_memory_variables({"input": "Tell me about memory decay"})
    print(f"\nRetrieved context for 'memory decay':")
    print(context["history"])

    # -- Retrieving context for a different query -----------------------------
    context = memory.load_memory_variables({"input": "Does it need internet?"})
    print(f"\nRetrieved context for 'Does it need internet?':")
    print(context["history"])

    # -- Integration with a LangChain chain (conceptual) ----------------------
    # In a real application, you would use it like this:
    #
    #   from langchain.chains import LLMChain
    #   from langchain_openai import ChatOpenAI
    #   from langchain.prompts import PromptTemplate
    #
    #   llm = ChatOpenAI(model="gpt-4")
    #   prompt = PromptTemplate(
    #       input_variables=["history", "input"],
    #       template="Previous context:\n{history}\n\nHuman: {input}\nAI:",
    #   )
    #   chain = LLMChain(llm=llm, prompt=prompt, memory=memory)
    #   response = chain.run("What did we discuss about forgetting?")

    print("\nDone!")


if __name__ == "__main__":
    main()
