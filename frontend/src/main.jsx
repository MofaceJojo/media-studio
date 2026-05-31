import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowsClockwise,
  CheckCircle,
  CloudSlash,
  FilmSlate,
  GearSix,
  ListChecks,
  MicrophoneStage,
  Question,
  Sparkle,
  WarningCircle,
} from "@phosphor-icons/react";
import "./styles.css";

const API = "http://127.0.0.1:8710/api";

const request = async (path, options = {}) => {
  const response = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
};

function HelpButton({ children }) {
  return (
    <details className="help">
      <summary aria-label="Show configuration note">
        <Question size={14} weight="bold" />
      </summary>
      <p>{children}</p>
    </details>
  );
}

function Field({ label, help, children }) {
  return (
    <label className="field">
      <span>
        {label}
        {help ? <HelpButton>{help}</HelpButton> : null}
      </span>
      {children}
    </label>
  );
}

function Result({ result }) {
  if (!result) return null;
  const Icon = result.ok ? CheckCircle : WarningCircle;
  return (
    <div className={`result ${result.ok ? "ok" : "bad"}`}>
      <Icon size={18} weight="fill" />
      <span>{result.message}</span>
    </div>
  );
}

function App() {
  const [providers, setProviders] = useState([]);
  const [workflows, setWorkflows] = useState([]);
  const [ttsProviders, setTtsProviders] = useState([]);
  const [llm, setLlm] = useState({ provider: "openrouter", api_key: "", base_url: "", model: "" });
  const [models, setModels] = useState([]);
  const [material, setMaterial] = useState({ provider: "pexels", api_keys: "", query: "city night", aspect: "portrait" });
  const [comfy, setComfy] = useState({ base_url: "http://127.0.0.1:8188", api_key: "" });
  const [tts, setTts] = useState({ provider: "edge", text: "Morpheus Video Studio 配音测试。", voice: "zh-CN-XiaoxiaoNeural" });
  const [results, setResults] = useState({});
  const [busy, setBusy] = useState("");

  useEffect(() => {
    Promise.all([
      request("/llm/providers"),
      request("/comfyui/workflows"),
      request("/tts/providers"),
    ]).then(([providerData, workflowData, ttsData]) => {
      setProviders(providerData);
      setWorkflows(workflowData.selfhost || []);
      setTtsProviders(ttsData.providers || []);
    });
  }, []);

  const selectedProvider = useMemo(
    () => providers.find((provider) => provider.id === llm.provider),
    [providers, llm.provider]
  );

  useEffect(() => {
    if (!selectedProvider) return;
    setLlm((current) => ({
      ...current,
      base_url: selectedProvider.base_url,
      model: selectedProvider.default_model,
    }));
    setModels(selectedProvider.fallback_models || []);
  }, [selectedProvider?.id]);

  const run = async (key, task) => {
    setBusy(key);
    setResults((current) => ({ ...current, [key]: null }));
    try {
      const data = await task();
      setResults((current) => ({ ...current, [key]: data }));
    } catch (error) {
      setResults((current) => ({ ...current, [key]: { ok: false, message: error.message } }));
    } finally {
      setBusy("");
    }
  };

  const loadModels = () =>
    run("models", async () => {
      const data = await request("/llm/models", { method: "POST", body: JSON.stringify(llm) });
      setModels(data.models || []);
      return { ok: true, message: `Loaded ${data.models?.length || 0} models.` };
    });

  const testLlm = () => run("llm", () => request("/llm/test", { method: "POST", body: JSON.stringify(llm) }));
  const testMaterials = () =>
    run("materials", () =>
      request("/materials/test", {
        method: "POST",
        body: JSON.stringify({ ...material, api_keys: material.api_keys.split(/[,\n]/).map((item) => item.trim()).filter(Boolean) }),
      })
    );
  const testComfy = () => run("comfy", () => request("/comfyui/test", { method: "POST", body: JSON.stringify(comfy) }));
  const testTts = () => run("tts", () => request("/tts/test", { method: "POST", body: JSON.stringify(tts) }));

  return (
    <main className="shell">
      <aside className="rail">
        <div className="brand">
          <div className="mark"><FilmSlate size={25} weight="duotone" /></div>
          <div>
            <strong>Morpheus</strong>
            <span>Video Studio</span>
          </div>
        </div>
        <nav>
          <a className="active"><Sparkle size={18} /> Studio</a>
          <a><ListChecks size={18} /> Pipelines</a>
          <a><GearSix size={18} /> Settings</a>
        </nav>
        <div className="no-cloud">
          <CloudSlash size={20} />
          <span>RunningHub removed. Local ComfyUI only.</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">Unified short-video engine</p>
            <h1>Morpheus Video Studio</h1>
          </div>
          <button className="primary"><FilmSlate size={18} weight="fill" /> New video</button>
        </header>

        <section className="matrix">
          <article className="panel llm-panel">
            <div className="panel-title">
              <h2>LLM Provider</h2>
              <Result result={results.llm || results.models} />
            </div>
            <div className="grid two">
              <Field label="Provider" help="Selecting a provider fills its normal OpenAI-compatible Base URL and default model.">
                <select value={llm.provider} onChange={(event) => setLlm({ ...llm, provider: event.target.value })}>
                  {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
                </select>
              </Field>
              <Field label="API Key" help="Stored only in this browser state in this prototype. Use the test button before generation.">
                <input type="password" value={llm.api_key} onChange={(event) => setLlm({ ...llm, api_key: event.target.value })} />
              </Field>
              <Field label="Base URL" help="You can override it for proxies or compatible gateways.">
                <input value={llm.base_url} onChange={(event) => setLlm({ ...llm, base_url: event.target.value })} />
              </Field>
              <Field label="Model" help="Load models from the API, pick a fallback, or type a custom model name.">
                <input list="model-list" value={llm.model} onChange={(event) => setLlm({ ...llm, model: event.target.value })} />
                <datalist id="model-list">{models.map((model) => <option key={model} value={model} />)}</datalist>
              </Field>
            </div>
            <div className="actions">
              <button onClick={loadModels} disabled={busy === "models"}><ArrowsClockwise size={17} /> Load models</button>
              <button onClick={testLlm} disabled={busy === "llm"}><CheckCircle size={17} /> Test LLM</button>
            </div>
          </article>

          <article className="panel">
            <div className="panel-title">
              <h2>Video Sources</h2>
              <Result result={results.materials} />
            </div>
            <div className="grid two">
              <Field label="Source" help="Free online stock libraries are kept from MoneyPrinterPlus and MoneyPrinterTurbo.">
                <select value={material.provider} onChange={(event) => setMaterial({ ...material, provider: event.target.value })}>
                  <option value="pexels">Pexels</option>
                  <option value="pixabay">Pixabay</option>
                </select>
              </Field>
              <Field label="Aspect" help="Used to request clips close to the target short-video frame.">
                <select value={material.aspect} onChange={(event) => setMaterial({ ...material, aspect: event.target.value })}>
                  <option value="portrait">9:16</option>
                  <option value="landscape">16:9</option>
                  <option value="square">1:1</option>
                </select>
              </Field>
              <Field label="API Keys" help="Comma or newline separated. The backend rotates keys deterministically.">
                <textarea value={material.api_keys} onChange={(event) => setMaterial({ ...material, api_keys: event.target.value })} />
              </Field>
              <Field label="Test query" help="A lightweight search validates the key and response format.">
                <input value={material.query} onChange={(event) => setMaterial({ ...material, query: event.target.value })} />
              </Field>
            </div>
            <div className="actions">
              <button onClick={testMaterials} disabled={busy === "materials"}><CheckCircle size={17} /> Test source</button>
            </div>
          </article>

          <article className="panel">
            <div className="panel-title">
              <h2>Local ComfyUI</h2>
              <Result result={results.comfy} />
            </div>
            <div className="grid two">
              <Field label="Server URL" help="Only local or self-hosted ComfyUI is exposed. Cloud RunningHub workflows are not copied.">
                <input value={comfy.base_url} onChange={(event) => setComfy({ ...comfy, base_url: event.target.value })} />
              </Field>
              <Field label="API Key" help="Optional ComfyUI key if your local server requires one.">
                <input type="password" value={comfy.api_key} onChange={(event) => setComfy({ ...comfy, api_key: event.target.value })} />
              </Field>
            </div>
            <div className="workflow-strip">
              {workflows.slice(0, 8).map((workflow) => <span key={workflow}>{workflow}</span>)}
            </div>
            <div className="actions">
              <button onClick={testComfy} disabled={busy === "comfy"}><CheckCircle size={17} /> Test ComfyUI</button>
            </div>
          </article>

          <article className="panel">
            <div className="panel-title">
              <h2>Voice Synthesis</h2>
              <Result result={results.tts} />
            </div>
            <div className="grid two">
              <Field label="Provider" help="Only local or free options are kept. Paid cloud TTS providers are intentionally excluded.">
                <select value={tts.provider} onChange={(event) => setTts({ ...tts, provider: event.target.value })}>
                  {ttsProviders.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
                </select>
              </Field>
              <Field label="Voice" help="Edge voice id or local voice identifier.">
                <input value={tts.voice} onChange={(event) => setTts({ ...tts, voice: event.target.value })} />
              </Field>
              <Field label="Preview text" help="The one-click test creates a short Edge TTS preview or validates local-provider selection.">
                <textarea value={tts.text} onChange={(event) => setTts({ ...tts, text: event.target.value })} />
              </Field>
              <div className="voice-list">
                <MicrophoneStage size={22} />
                <span>Edge TTS, ChatTTS, GPT-SoVITS, CosyVoice, ComfyUI TTS</span>
              </div>
            </div>
            <div className="actions">
              <button onClick={testTts} disabled={busy === "tts"}><CheckCircle size={17} /> Test voice</button>
            </div>
          </article>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
