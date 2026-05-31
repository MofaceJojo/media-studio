import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowsClockwise,
  CheckCircle,
  CloudSlash,
  DownloadSimple,
  FileText,
  FilmSlate,
  GearSix,
  ListChecks,
  MagicWand,
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
  const [tts, setTts] = useState({
    provider: "edge",
    text: "Morpheus Video Studio 配音测试。",
    voice: "zh-CN-XiaoxiaoNeural",
    base_url: "http://127.0.0.1:9880",
  });
  const [video, setVideo] = useState({
    title: "Morpheus Video Studio",
    topic: "普通人如何用长期主义改变人生",
    script: "",
    aspect: "portrait",
    seconds_per_scene: 3.2,
    voice_provider: "edge",
    voice: "zh-CN-XiaoxiaoNeural",
    local_voice_url: "http://127.0.0.1:9880",
    enable_subtitles: true,
    local_media_paths: "",
    source_file_paths: "",
    source_file_skill: "video_script",
  });
  const [generated, setGenerated] = useState(null);
  const [writing, setWriting] = useState({
    mode: "video_script",
    tone: "clean",
    text: "一个普通人因为一次失败，重新审视自己的选择，并慢慢找到真正适合自己的道路。",
    source_file_paths: "",
  });
  const [writingResult, setWritingResult] = useState("");
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
  const runWriting = () =>
    run("writing", async () => {
      const data = await request("/writing/run", { method: "POST", body: JSON.stringify(writing) });
      setWritingResult(data.text || "");
      if (writing.mode === "video_script") {
        setVideo((current) => ({ ...current, script: data.text || current.script }));
      }
      const fileCount = data.source_files_used?.length || 0;
      return {
        ok: data.ok,
        message: data.ok ? `Writing tool finished${fileCount ? ` with ${fileCount} file(s).` : "."}` : "No text generated.",
      };
    });
  const generateVideo = () =>
    run("video", async () => {
      const data = await request("/video/generate", { method: "POST", body: JSON.stringify(video) });
      setGenerated(data);
      return { ok: data.ok, message: data.message };
    });

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

        <section className="studio-grid">
          <article className="panel compose-panel">
            <div className="panel-title">
              <h2>Local Video Generator</h2>
              <Result result={results.video} />
            </div>
            <div className="grid two">
              <Field label="Title" help="Used on generated slides and metadata.">
                <input value={video.title} onChange={(event) => setVideo({ ...video, title: event.target.value })} />
              </Field>
              <Field label="Aspect" help="Portrait is best for short-video platforms.">
                <select value={video.aspect} onChange={(event) => setVideo({ ...video, aspect: event.target.value })}>
                  <option value="portrait">9:16</option>
                  <option value="landscape">16:9</option>
                  <option value="square">1:1</option>
                </select>
              </Field>
              <Field label="Voiceover" help="Edge TTS is free and classic. None keeps generation fully offline. Local API posts to /tts.">
                <select value={video.voice_provider} onChange={(event) => setVideo({ ...video, voice_provider: event.target.value })}>
                  <option value="edge">Edge TTS</option>
                  <option value="local_api">Local Voice API</option>
                  <option value="none">None</option>
                </select>
              </Field>
              <Field label="Voice ID" help="For Edge TTS, use a voice such as zh-CN-XiaoxiaoNeural or en-US-JennyNeural.">
                <input value={video.voice} onChange={(event) => setVideo({ ...video, voice: event.target.value })} />
              </Field>
              <Field label="Local Voice URL" help="For Omni Voice-style services. Morpheus sends POST /tts with text and voice.">
                <input value={video.local_voice_url} onChange={(event) => setVideo({ ...video, local_voice_url: event.target.value })} />
              </Field>
              <Field label="Subtitles" help="Creates a standard SRT file and burns readable captions into the generated video.">
                <span className="checkbox-row">
                  <input
                    type="checkbox"
                    checked={video.enable_subtitles}
                    onChange={(event) => setVideo({ ...video, enable_subtitles: event.target.checked })}
                  />
                  <span>Burn captions into video</span>
                </span>
              </Field>
              <Field label="Local media" help="Optional. Paste one local image or video file path per line; Morpheus cycles them as scene backgrounds.">
                <textarea
                  value={video.local_media_paths}
                  onChange={(event) => setVideo({ ...video, local_media_paths: event.target.value })}
                  placeholder="/Users/you/Videos/background.mp4"
                />
              </Field>
              <Field label="Text files" help="Optional. Paste local .txt or .md paths; Morpheus can turn drafts or novel fragments into scene scripts before rendering.">
                <textarea
                  value={video.source_file_paths}
                  onChange={(event) => setVideo({ ...video, source_file_paths: event.target.value })}
                  placeholder="/Users/you/Documents/story.md"
                />
              </Field>
              <Field label="File skill" help="Applied when Script is empty and text files are provided.">
                <select value={video.source_file_skill} onChange={(event) => setVideo({ ...video, source_file_skill: event.target.value })}>
                  <option value="video_script">Make video script</option>
                  <option value="polish">Polish into scenes</option>
                  <option value="novel_outline">Novel outline</option>
                </select>
              </Field>
              <Field label="Topic" help="If script is empty, Morpheus creates a concise local script from this topic.">
                <textarea value={video.topic} onChange={(event) => setVideo({ ...video, topic: event.target.value })} />
              </Field>
              <Field label="Script" help="One line becomes one scene. You can paste polished text or use the writing module below.">
                <textarea value={video.script} onChange={(event) => setVideo({ ...video, script: event.target.value })} />
              </Field>
            </div>
            <div className="actions">
              <button className="primary" onClick={generateVideo} disabled={busy === "video"}>
                <FilmSlate size={17} weight="fill" /> Generate MP4
              </button>
            </div>
            {generated?.video_url ? (
              <div className="output-video">
                <video src={`http://127.0.0.1:8710${generated.video_url}`} controls />
                <a href={`http://127.0.0.1:8710${generated.video_url}`} target="_blank" rel="noreferrer">
                  <DownloadSimple size={17} /> Open video
                </a>
                {generated.subtitle_path ? <span className="output-note">SRT generated with the final video.</span> : null}
                {generated.media_used?.length ? <span className="output-note">Local media: {generated.media_used.length} scene link(s).</span> : null}
                {generated.source_files_used?.length ? <span className="output-note">Text files: {generated.source_files_used.length} loaded.</span> : null}
              </div>
            ) : null}
          </article>

          <article className="panel writing-panel">
            <div className="panel-title">
              <h2>Novel & Polish Lab</h2>
              <Result result={results.writing} />
            </div>
            <div className="grid">
              <Field label="Skill" help="Local writing tools for novel outlining, polishing, and turning prose into short-video scripts.">
                <select value={writing.mode} onChange={(event) => setWriting({ ...writing, mode: event.target.value })}>
                  <option value="video_script">Make video script</option>
                  <option value="polish">Polish text</option>
                  <option value="novel_outline">Novel outline</option>
                </select>
              </Field>
              <Field label="Tone" help="Clean is direct, Novel is more atmospheric, Viral is punchier.">
                <select value={writing.tone} onChange={(event) => setWriting({ ...writing, tone: event.target.value })}>
                  <option value="clean">Clean</option>
                  <option value="novel">Novel</option>
                  <option value="viral">Viral</option>
                </select>
              </Field>
              <Field label="Source text" help="Paste a novel fragment, outline, rough idea, or existing script.">
                <textarea value={writing.text} onChange={(event) => setWriting({ ...writing, text: event.target.value })} />
              </Field>
              <Field label="Source files" help="Optional local .txt or .md files. The selected skill reads them before generating the result.">
                <textarea
                  value={writing.source_file_paths}
                  onChange={(event) => setWriting({ ...writing, source_file_paths: event.target.value })}
                  placeholder="/Users/you/Documents/chapter-01.txt"
                />
              </Field>
              <button onClick={runWriting} disabled={busy === "writing"}>
                <MagicWand size={17} /> Run writing skill
              </button>
              <textarea className="writing-output" value={writingResult} readOnly placeholder="Result appears here." />
              <button onClick={() => setVideo({ ...video, script: writingResult })} disabled={!writingResult}>
                <FileText size={17} /> Use as script
              </button>
            </div>
          </article>
        </section>

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
              <Field label="Provider" help="Only free or local voice options are kept. Paid cloud voice services are excluded.">
                <select value={tts.provider} onChange={(event) => setTts({ ...tts, provider: event.target.value })}>
                  {ttsProviders.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
                </select>
              </Field>
              <Field label="Voice" help="Edge voice id, ComfyUI workflow voice value, or a local voice identifier.">
                <input value={tts.voice} onChange={(event) => setTts({ ...tts, voice: event.target.value })} />
              </Field>
              <Field label="Local API URL" help="Reserved for local voice engines such as Omni Voice. The test checks /health first, then the base URL.">
                <input value={tts.base_url} onChange={(event) => setTts({ ...tts, base_url: event.target.value })} />
              </Field>
              <Field label="Preview text" help="The one-click test creates a short Edge TTS preview or validates the selected local voice endpoint.">
                <textarea value={tts.text} onChange={(event) => setTts({ ...tts, text: event.target.value })} />
              </Field>
              <div className="voice-list">
                <MicrophoneStage size={22} />
                <span>Edge TTS, ComfyUI TTS workflow, Local Voice API for Omni Voice-style services</span>
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
