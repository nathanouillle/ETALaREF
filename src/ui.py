import os
import time
import base64
import uuid
from typing import Callable, Optional

import ipywidgets as widgets
from IPython.display import display, HTML, Javascript


def chatbot_ui(
    bot: Callable[[str], str],
    height: str = "300px",
    record_seconds: int = 5,
    auto_transcribe: bool = True,
    whisper_model_size: str = "base",
):
    """
    Chat UI with text input + voice recording (browser) and optional Whisper transcription.

    Requirements / notes:
      - Best run in CLASSIC Jupyter Notebook (not VS Code / not JupyterLab) so the JS->Python bridge works.
      - Open via http://localhost:PORT (Chrome) and File -> Trust Notebook so mic prompts appear.
      - If the JS->Python bridge isn't available, this falls back to downloading the WAV; you can then Upload it.
      - For MP3/WEBM uploads or recordings, Whisper relies on ffmpeg. Ensure ffmpeg is available in PATH.
    """
    # === Widgets ===
    chat_output = widgets.Output(
        layout=widgets.Layout(width="100%", height=height, border="1px solid #444", overflow="auto")
    )
    chat_output.add_class("chat-container")

    user_input = widgets.Text(placeholder="Type a message…", continuous_update=False)
    send_button = widgets.Button(description="Send", button_style="success")
    record_button = widgets.Button(description="🎙️ Record", tooltip="Record voice")
    upload = widgets.FileUpload(accept="audio/*", multiple=False, description="Upload audio")

    # === State ===
    ui_id = uuid.uuid4().hex
    voices_dir = os.path.abspath("voices")
    os.makedirs(voices_dir, exist_ok=True)

    chat_history = []  # list of dicts: {"sender": "user"/"bot", "text": str, "audio_path": Optional[str]}
    whisper_model_obj = None

    # === Rendering ===
    def render_chat():
        with chat_output:
            chat_output.clear_output(wait=True)
            html = ["<div style='display:flex; flex-direction:column; gap:8px; font:14px system-ui,Segoe UI,Arial;'>"]
            for m in chat_history:
                is_user = (m["sender"] == "user")
                bg = "#DCF8C6" if is_user else "#E8E8E8"
                align = "flex-end" if is_user else "flex-start"
                html.append(
                    f"<div style='align-self:{align}; background:{bg}; padding:8px 10px; "
                    f"border-radius:10px; max-width:72%; word-wrap:break-word;'>"
                )
                if m.get("text"):
                    html.append(f"<div style='white-space:pre-wrap'>{m['text']}</div>")
                if m.get("audio_path"):
                    try:
                        with open(m["audio_path"], "rb") as f:
                            b64 = base64.b64encode(f.read()).decode("ascii")
                        # Guess MIME by extension (fallback to wav)
                        ext = os.path.splitext(m["audio_path"])[1].lower()
                        mime = "audio/wav"
                        if ext in (".mp3",):
                            mime = "audio/mpeg"
                        elif ext in (".webm",):
                            mime = "audio/webm"
                        elif ext in (".ogg",):
                            mime = "audio/ogg"
                        html.append(
                            f"<audio controls style='width:100%; margin-top:6px' "
                            f"src='data:{mime};base64,{b64}'></audio>"
                        )
                    except Exception as e:
                        html.append(f"<div style='color:#b00'>[Audio load failed: {e}]</div>")
                html.append("</div>")
            html.append("</div>")
            display(HTML("".join(html)))
            display(Javascript("const c=document.querySelector('.chat-container'); if(c) c.scrollTop=c.scrollHeight;"))

    # === Bot plumbing ===
    def send_message(msg: str, audio_path: Optional[str] = None):
        msg = (msg or "").strip()
        if not msg and not audio_path:
            return
        chat_history.append({"sender": "user", "text": msg, "audio_path": audio_path})
        try:
            bot_out = bot(msg if msg else "")
        except Exception as e:
            bot_out = f"[bot error: {e}]"
        chat_history.append({"sender": "bot", "text": bot_out, "audio_path": None})
        render_chat()
        user_input.value = ""

    # === Optional ASR ===
    def transcribe_if_possible(wav_path: str) -> Optional[str]:
        nonlocal whisper_model_obj
        if not auto_transcribe:
            return None
        try:
            import whisper  # lazy import
        except Exception:
            return None
        try:
            if whisper_model_obj is None:
                whisper_model_obj = whisper.load_model(whisper_model_size)
            result = whisper_model_obj.transcribe(wav_path)
            text = (result.get("text") or "").strip()
            return text or None
        except Exception:
            return None

    # === Receiver called from JS ===
    def _receive_audio_b64_and_process(b64: str, filename: str):
        path = os.path.join(voices_dir, filename)
        try:
            with open(path, "wb") as f:
                f.write(base64.b64decode(b64))
        except Exception as e:
            chat_history.append({"sender": "bot", "text": f"[Failed to save audio: {e}]", "audio_path": None})
            render_chat()
            return
        transcript = transcribe_if_possible(path)
        user_text = transcript if transcript else "[Voice message]"
        send_message(user_text, audio_path=path)

    # Register receiver globally so JS can call it
    recv_func_name = f"_chatbot_recv_{ui_id}"
    globals()[recv_func_name] = _receive_audio_b64_and_process

    # === Recorder JS with strong feedback + fallback ===
    def start_record_js(seconds: int):
        fname = f"voice_{int(time.time())}_{ui_id}.wav"
        js = f"""
(async () => {{
  const sec = {int(seconds)};
  const filename = {repr(fname)};

  // Visual feedback on the button (disable while recording)
  const btns = [...document.querySelectorAll('button')];
  const recBtn = btns.find(b => b.textContent && b.textContent.includes('Record'));
  if (recBtn) {{ recBtn.disabled = true; recBtn.textContent = `🎙️ Recording... ${{sec}}s`; }}

  const classicOK = !!(window.Jupyter && Jupyter.notebook && Jupyter.notebook.kernel);
  console.log("[rec] env classicOK =", classicOK);

  // Check mic API
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {{
    alert("Microphone API not available (need Chrome on localhost/https).");
    if (recBtn) {{ recBtn.disabled = false; recBtn.textContent = "🎙️ Record"; }}
    return;
  }}

  // Mic permission probe
  try {{
    if (navigator.permissions && navigator.permissions.query) {{
      const perm = await navigator.permissions.query({{name: 'microphone'}});
      console.log("[rec] mic perm:", perm.state);
    }}
  }} catch(e) {{
    console.log("[rec] permissions.query failed:", e);
  }}

  // Capture
  let stream;
  try {{
    stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
  }} catch (e) {{
    alert("Microphone permission denied: " + e);
    if (recBtn) {{ recBtn.disabled = false; recBtn.textContent = "🎙️ Record"; }}
    return;
  }}

  // Record compressed chunks
  const mr = new MediaRecorder(stream);
  const chunks = [];
  mr.ondataavailable = e => {{ if (e.data && e.data.size) chunks.push(e.data); }};
  mr.start();
  console.log("[rec] started MediaRecorder for", sec, "s");
  await new Promise(r => setTimeout(r, sec*1000));
  mr.stop();

  const blob = await new Promise(r => mr.onstop = () => r(new Blob(chunks, {{ type: 'audio/webm' }})));
  stream.getTracks().forEach(t => t.stop());
  console.log("[rec] recorded blob:", blob.type, blob.size);

  // Decode to PCM
  try {{
    const arrayBuffer = await blob.arrayBuffer();
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)({{ sampleRate: 44100 }});
    const audioBuf = await audioCtx.decodeAudioData(arrayBuffer);
    const mono = audioBuf.numberOfChannels ? audioBuf.getChannelData(0) : new Float32Array(0);
    audioCtx.close();

    // WAV encode 16-bit PCM
    function floatTo16BitPCM(f32) {{
      const out = new Int16Array(f32.length);
      for (let i = 0; i < f32.length; i++) {{
        const s = Math.max(-1, Math.min(1, f32[i]));
        out[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }}
      return out;
    }}
    function writeString(view, offset, str) {{
      for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    }}
    function encodeWAV(samples, sampleRate) {{
      const pcm = floatTo16BitPCM(samples);
      const buffer = new ArrayBuffer(44 + pcm.length * 2);
      const view = new DataView(buffer);
      writeString(view, 0, 'RIFF');
      view.setUint32(4, 36 + pcm.length * 2, true);
      writeString(view, 8, 'WAVE');
      writeString(view, 12, 'fmt ');
      view.setUint32(16, 16, true);
      view.setUint16(20, 1, true); // PCM
      writeString(view, 36, 'data');
      view.setUint16(22, 1, true); // mono
      view.setUint32(24, sampleRate, true);
      view.setUint32(28, sampleRate * 2, true); // byte rate
      view.setUint16(32, 2, true); // block align
      view.setUint16(34, 16, true); // bits per sample
      view.setUint32(40, pcm.length * 2, true);
      new Int16Array(buffer, 44, pcm.length).set(pcm);
      return buffer;
    }}

    const wavBuffer = encodeWAV(mono, 44100);
    const bytes = new Uint8Array(wavBuffer);
    let bin = ''; for (let i=0;i<bytes.length;i++) bin += String.fromCharCode(bytes[i]);
    const b64 = btoa(bin);

    if (classicOK) {{
      const py = "{recv_func_name}(" + JSON.stringify(b64) + "," + JSON.stringify("{fname}") + ")";
      console.log("[rec] sending to Python via kernel.execute");
      Jupyter.notebook.kernel.execute(py);
    }} else {{
      console.warn("[rec] classic bridge not available; offering download instead.");
      const a = document.createElement('a');
      a.href = 'data:audio/wav;base64,' + b64;
      a.download = filename;
      a.click();
      alert("Saved recording as download. Upload it via the 'Upload audio' button.");
    }}
  }} catch(e) {{
    console.error("[rec] decode/encode failed:", e);
    alert("Recording failed: " + e);
  }} finally {{
    if (recBtn) {{ recBtn.disabled = false; recBtn.textContent = "🎙️ Record"; }}
  }}
}})().catch(e => {{
  console.error("[rec] top-level error:", e);
  alert("Recorder error: " + e);
  const btns = [...document.querySelectorAll('button')];
  const recBtn = btns.find(b => b.textContent && b.textContent.includes('Recording'));
  if (recBtn) {{ recBtn.disabled = false; recBtn.textContent = "🎙️ Record"; }}
}});
"""
        display(Javascript(js))

    # === Helpers ===
    def _extract_upload_items(value):
        """
        Normalize ipywidgets FileUpload.value to a list of dicts.
        - ipywidgets <=7: value is a dict {filename: {...}}
        - ipywidgets 8+: value is a tuple of dicts
        """
        if isinstance(value, dict):
            return list(value.values())
        if isinstance(value, (tuple, list)):
            return list(value)
        return []

    # === Events ===
    def on_click_send(_):
        send_message(user_input.value)

    def on_submit_text(_):
        send_message(user_input.value)

    def on_click_record(_):
        start_record_js(record_seconds)

    def on_upload_change(_):
        items = _extract_upload_items(upload.value)
        if not items:
            return

        # take the latest file (in case widget still had previous content)
        up = items[-1]
        raw = up.get("content", b"")
        if isinstance(raw, memoryview):
            raw = raw.tobytes()

        original_name = up.get("name", f"upload_{int(time.time())}.wav")
        ext = os.path.splitext(original_name)[1] or ".wav"
        fname = f"upload_{int(time.time())}_{ui_id}{ext}"
        path = os.path.join(voices_dir, fname)

        try:
            with open(path, "wb") as f:
                f.write(raw)
        except Exception as e:
            chat_history.append({"sender": "bot", "text": f"[Failed to save upload: {e}]", "audio_path": None})
            render_chat()
            return

        transcript = transcribe_if_possible(path)
        text = transcript if transcript else f"[Uploaded {original_name}]"
        send_message(text, audio_path=path)

        # clear widget value for both APIs
        try:
            upload.value = ()
        except Exception:
            try:
                upload.value.clear()
            except Exception:
                pass

    send_button.on_click(on_click_send)
    user_input.on_submit(on_submit_text)
    record_button.on_click(on_click_record)
    upload.observe(on_upload_change, names="value")

    # === Layout ===
    controls_row = widgets.HBox([user_input, send_button, record_button, upload])
    chat_ui = widgets.VBox([chat_output, controls_row])
    display(chat_ui)
    render_chat()
