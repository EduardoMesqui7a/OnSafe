from __future__ import annotations

from datetime import datetime

import streamlit as st

try:
    import av
except Exception:  # pragma: no cover - optional dependency
    av = None

try:
    from streamlit_webrtc import VideoProcessorBase, WebRtcMode, webrtc_streamer
except Exception:  # pragma: no cover - optional dependency
    VideoProcessorBase = object
    WebRtcMode = None
    webrtc_streamer = None

from app.core.config import get_settings
from app.core.enums import Protocol
from app.core.schemas import CameraConfig
from app.integrations.streamlit_contracts import OnSafeBackend

RTC_CONFIGURATION = {
    "iceServers": [
        {"urls": ["stun:stun.l.google.com:19302"]},
        {"urls": ["stun:stun1.l.google.com:19302"]},
    ]
}

BROWSER_MEDIA_CONSTRAINTS = {
    "video": {
        "width": {"ideal": 240},
        "height": {"ideal": 180},
        "frameRate": {"ideal": 6, "max": 10},
    },
    "audio": False,
}


@st.cache_resource
def get_backend() -> OnSafeBackend:
    settings = get_settings()
    return OnSafeBackend(settings)


def render_camera_form(backend: OnSafeBackend) -> None:
    st.subheader("Cadastro de cameras")
    source_mode = st.radio(
        "Origem da camera",
        options=["IP/RTSP", "Webcam do navegador", "Webcam local da maquina"],
        horizontal=True,
    )

    with st.form("camera_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Nome da camera", placeholder="Portaria")
            if source_mode == "IP/RTSP":
                host = st.text_input("IP ou host", placeholder="192.168.0.10")
                port = st.number_input("Porta", min_value=0, max_value=65535, value=554)
                protocol = st.selectbox("Protocolo", options=[item.value for item in Protocol], index=0)
            elif source_mode == "Webcam local da maquina":
                host = "0"
                port = 0
                protocol = Protocol.RTSP.value
                st.text_input("IP ou host", value="0", disabled=True)
                st.number_input("Porta", min_value=0, max_value=65535, value=0, disabled=True)
                st.selectbox("Protocolo", options=[Protocol.RTSP.value], index=0, disabled=True)
            else:
                host = "__browser__"
                port = 0
                protocol = Protocol.RTSP.value
                st.text_input("IP ou host", value="__browser__", disabled=True)
                st.number_input("Porta", min_value=0, max_value=65535, value=0, disabled=True)
                st.selectbox("Protocolo", options=[Protocol.RTSP.value], index=0, disabled=True)
        with col2:
            if source_mode == "IP/RTSP":
                username = st.text_input("Usuario")
                password = st.text_input("Senha", type="password")
                stream_path = st.text_input("Caminho do stream", placeholder="stream1")
            else:
                username = None
                password = None
                stream_path = ""
                st.text_input("Usuario", value="", disabled=True)
                st.text_input("Senha", value="", type="password", disabled=True)
                st.text_input("Caminho do stream", value="", disabled=True)
            required_ppe = st.multiselect("EPIs obrigatorios", options=["helmet", "vest"], default=["helmet", "vest"])
        submitted = st.form_submit_button("Cadastrar camera")
        if submitted:
            if not name:
                st.error("Informe o nome da camera.")
            else:
                try:
                    camera = backend.register_camera(
                        CameraConfig(
                            name=name,
                            host=host,
                            port=int(port),
                            username=username or None,
                            password=password or None,
                            protocol=Protocol(protocol),
                            stream_path=stream_path,
                            required_ppe=list(required_ppe),
                        )
                    )
                    st.success(f"Camera cadastrada com ID {camera.id}.")
                except ValueError as exc:
                    st.error(str(exc))


def _render_status_badge(health: str) -> str:
    mapping = {
        "online": "ONLINE",
        "offline": "OFFLINE",
        "degraded": "INSTAVEL",
        "starting": "INICIANDO",
        "stopped": "PARADA",
    }
    return mapping.get(health, health.upper())


@st.fragment(run_every=2)
def _render_browser_status(backend: OnSafeBackend, camera_id: int) -> None:
    runtime = backend.get_browser_runtime(camera_id)
    status = runtime.get_status()
    if status.status_message:
        st.warning(status.status_message)
    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Capture FPS", f"{status.capture_fps:.1f}")
    metric2.metric("Inference FPS", f"{status.inference_fps:.1f}")
    metric3.metric("Tracks ativos", status.active_tracks)
    metric4.metric("Ultima decisao", status.latest_decision.value if status.latest_decision else "n/a")

    packet = runtime.get_frame()
    if packet is not None:
        st.image(packet.frame, channels="BGR", caption=f"Preview processado: {packet.timestamp}", width=240)

    tracks = runtime.list_active_tracks()
    if tracks:
        st.write("Pessoas rastreadas:")
        for track in tracks:
            st.write(f"- {track.label} | Track {track.track_id} | hits {track.stability_hits}")
    with st.expander("Diagnostico detalhado", expanded=True):
        st.json(status.diagnostics)


def render_browser_camera(backend: OnSafeBackend, camera) -> None:
    st.info("Modo navegador: funciona no Streamlit Cloud e usa a webcam do browser do usuario.")
    runtime = backend.get_browser_runtime(camera.id)
    st.write(_render_status_badge(runtime.get_status().health.value))

    if webrtc_streamer is None or av is None:
        st.warning("streamlit-webrtc indisponivel neste ambiente. Usando captura pontual como fallback.")
        snapshot = st.camera_input("Capturar frame da webcam", key=f"browser_camera_fallback_{camera.id}")
        if snapshot is not None:
            st.image(snapshot, caption=f"Frame capturado em {datetime.now().strftime('%H:%M:%S')}")
            st.info("Para analise continua em nuvem, habilite streamlit-webrtc nas dependencias.")
        return

    def video_frame_callback(frame):
        image = frame.to_ndarray(format="bgr24")
        processed = runtime.process_frame(image)
        return av.VideoFrame.from_ndarray(processed, format="bgr24")

    ctx = webrtc_streamer(
        key=f"browser_webrtc_{camera.id}",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        media_stream_constraints=BROWSER_MEDIA_CONSTRAINTS,
        video_frame_callback=video_frame_callback,
        async_processing=True,
        video_html_attrs={
            "style": {
                "width": "100%",
                "maxWidth": "240px",
                "height": "160px",
                "margin": "0 auto",
            }
        },
    )
    st.caption(f"WebRTC ativo: {bool(ctx and ctx.state.playing)}")
    if not (ctx and ctx.state.playing):
        st.warning(
            "A conexao WebRTC ainda nao foi estabelecida. Clique em START, escolha a camera no navegador e aguarde alguns segundos. "
            "Se continuar falhando, a rede pode estar bloqueando a negociacao ICE/STUN."
        )
    _render_browser_status(backend, camera.id)
    st.caption("Ao manter o stream ativo, o backend continua analisando os frames, registrando eventos e gerando relatorios.")


@st.fragment(run_every=2)
def render_network_or_local_camera(backend: OnSafeBackend, camera) -> None:
    status = backend.get_camera_status(camera.id)
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.markdown(f"### {camera.name}")
        st.caption(camera.build_stream_url())
        if str(camera.host).strip() == "0":
            st.caption("Fonte local detectada: webcam da maquina que executa o app")
            st.warning(
                "Host 0 funciona apenas quando o app roda localmente na mesma maquina. "
                "No Streamlit Cloud, use a opcao Webcam do navegador ou uma camera IP/RTSP."
            )
        st.write(_render_status_badge(status.health.value))
    with col2:
        if st.button("Testar", key=f"test_{camera.id}"):
            result = backend.test_camera(
                CameraConfig(
                    name=camera.name,
                    host=camera.host,
                    port=camera.port,
                    username=camera.username,
                    password=camera.password,
                    protocol=camera.protocol,
                    stream_path=camera.stream_path,
                    enabled=camera.enabled,
                    required_ppe=camera.required_ppe,
                )
            )
            if result.success:
                latency = f" Latencia: {result.latency_ms:.0f} ms" if result.latency_ms is not None else ""
                st.success(f"{result.message}{latency}")
            else:
                st.warning(result.message)
    with col3:
        if st.button("Iniciar", key=f"start_{camera.id}"):
            st.info(backend.start_monitoring(camera.id).message)
    with col4:
        if st.button("Parar", key=f"stop_{camera.id}"):
            st.info(backend.stop_monitoring(camera.id).message)

    metric1, metric2, metric3, metric4 = st.columns(4)
    metric1.metric("Capture FPS", f"{status.capture_fps:.1f}")
    metric2.metric("Inference FPS", f"{status.inference_fps:.1f}")
    metric3.metric("Tracks ativos", status.active_tracks)
    metric4.metric("Ultima decisao", status.latest_decision.value if status.latest_decision else "n/a")
    if status.status_message:
        st.warning(status.status_message)

    packet = backend.get_live_snapshot(camera.id)
    if packet is not None:
        st.image(packet.frame, channels="BGR", caption=f"Ultimo frame: {packet.timestamp}", width=240)
    else:
        st.info("Sem frame disponivel ainda. Teste a conexao ou inicie o monitoramento.")

    tracks = backend.list_active_tracks(camera.id)
    if tracks:
        st.write("Pessoas rastreadas:")
        for track in tracks:
            st.write(f"- {track.label} | Track {track.track_id} | hits {track.stability_hits}")
    with st.expander("Diagnostico detalhado", expanded=False):
        st.json(status.diagnostics)


def render_monitoring(backend: OnSafeBackend) -> None:
    st.subheader("Monitoramento")
    cameras = backend.list_cameras()
    if not cameras:
        st.info("Cadastre ao menos uma camera para iniciar os testes no Streamlit.")
        return

    selected_ids = st.multiselect(
        "Cameras para exibir",
        options=[camera.id for camera in cameras],
        default=[camera.id for camera in cameras[:1]],
        format_func=lambda camera_id: next(camera.name for camera in cameras if camera.id == camera_id),
    )

    selected_cameras = [camera for camera in cameras if camera.id in selected_ids]
    if not selected_cameras:
        st.info("Selecione pelo menos uma camera para exibir.")
        return

    column_count = min(4, max(1, len(selected_cameras)))
    rows = [selected_cameras[index : index + column_count] for index in range(0, len(selected_cameras), column_count)]
    for row in rows:
        columns = st.columns(column_count)
        for idx, camera in enumerate(row):
            with columns[idx]:
                with st.container(border=True):
                    if camera.uses_browser_input():
                        st.markdown(f"### {camera.name}")
                        st.caption(camera.build_stream_url())
                        render_browser_camera(backend, camera)
                    else:
                        render_network_or_local_camera(backend, camera)


@st.fragment(run_every=2)
def render_events_and_reports(backend: OnSafeBackend) -> None:
    st.subheader("Eventos recentes")
    events = backend.list_recent_events(limit=20)
    if events:
        for event in events:
            with st.container(border=True):
                st.markdown(f"**{event.camera_name}** | {event.person_label}")
                st.write(
                    f"Estado: {event.decision_state.value} | EPI ausente: {', '.join(event.missing_ppe) or 'n/a'} | "
                    f"Confianca: {event.confidence_score:.2f} | Persistencia: {event.persistence_seconds:.1f}s"
                )
                st.caption(event.rationale)
                if event.image_path:
                    st.write(f"Evidencia: `{event.image_path}`")
    else:
        st.info("Nenhum evento salvo ainda.")

    st.subheader("Relatorios")
    if st.button("Gerar consolidado diario agora"):
        path = backend.build_daily_report()
        st.success(f"Relatorio diario gerado em {path}")

    reports = backend.list_reports(limit=20)
    if reports:
        for report in reports:
            st.write(f"- {report.title} | {report.report_kind.value} | {report.status.value}")
    else:
        st.info("Nenhum relatorio gerado ainda.")


def main() -> None:
    st.set_page_config(page_title="OnSafe", layout="wide")
    st.markdown(
        """
        <style>
        img {
            border-radius: 12px;
        }
        [data-testid="stMetric"] {
            padding: 0.25rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("OnSafe")
    st.caption("Monitoramento de cameras IP com IA de EPI")
    backend = get_backend()

    render_camera_form(backend)
    st.divider()
    render_monitoring(backend)
    st.divider()
    render_events_and_reports(backend)


if __name__ == "__main__":
    main()
