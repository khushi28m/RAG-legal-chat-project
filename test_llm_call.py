# scripts/test_llm_call.py
import sys
from pathlib import Path
import traceback
import inspect

# Ensure project root is on sys.path so `app` and `backend` imports work
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Try import the LLM client from common locations
LLMClient = None
import_err = None
for modpath in ("app.services.llm_client", "backend.app.services.llm_client"):
    try:
        module = __import__(modpath, fromlist=["LLMClient"])
        LLMClient = getattr(module, "LLMClient")
        print(f"Imported LLMClient from '{modpath}'")
        break
    except Exception as e:
        import_err = e

if LLMClient is None:
    print("Failed to import LLMClient. Last error:")
    traceback.print_exception(type(import_err), import_err, import_err.__traceback__)
    sys.exit(1)

# Run the test
print("\nCreating client and running a quick test call...\n")
try:
    # FIX: Using the corrected model name. It is now consistent across all files.
    client = LLMClient(model="gemini-2.5-flash", prefer="gemini")
    # print available info
    backend_used = getattr(client, "backend", None)
    model_used = getattr(client, "model", None)
    print("Client created OK.")
    print("Client backend:", backend_used)
    print("Client model:", model_used)

    # make a short test call
    prompt_msgs = [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Say hi in one short sentence."}
    ]
    print("\nSending test prompt to LLM...")
    reply = client.chat_completion(messages=prompt_msgs, max_tokens=512)
    print("\n=== LLM REPLY ===")
    print(reply)
    print("=================")

except Exception as exc:
    print("\nERROR OCCURRED:")
    traceback.print_exception(type(exc), exc, exc.__traceback__)

    # Helpful introspection for google.genai mismatches
    try:
        import google
        from google import genai  # type: ignore
        print("\n--- google.genai module info ---")
        try:
            print("genai module file:", genai.__file__)
        except Exception:
            print("genai.__file__ not available")
        names = [n for n in dir(genai) if not n.startswith("_")]
        print("genai attrs:", names)
        if hasattr(genai, "Client"):
            print("\n--- genai.Client attributes ---")
            try:
                client_cls = genai.Client
                print("Client callable, attributes:", [a for a in dir(client_cls) if not a.startswith("_")])
                # show signature if possible
                try:
                    print("Client signature:", inspect.signature(client_cls))
                except Exception:
                    pass
            except Exception as e2:
                print("Error inspecting genai.Client:", e2)
        else:
            print("genai.Client not present in this SDK build.")
    except Exception as e:
        print("\nCould not import or inspect google.genai:", e)

    # Also show openai availability for fallback debugging
    try:
        import openai
        print("\nopenai module available. openai.__version__ (if set):", getattr(openai, "__version__", "unknown"))
    except Exception as e:
        print("\nopenai not available:", e)

    sys.exit(2)