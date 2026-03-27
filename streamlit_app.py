from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
import streamlit.components.v1 as components

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


DECISION_LABELS = {
    "compliant": "Conforme",
    "suspected_non_compliance": "Não conformidade suspeita",
    "confirmed_non_compliance": "Não conformidade confirmada",
    "discarded_due_to_uncertainty": "Descartado por incerteza",
}

REPORT_KIND_LABELS = {
    "event": "Relatório de evento",
    "daily": "Consolidado diário",
}

REPORT_STATUS_LABELS = {
    "pending": "Pendente",
    "generated": "Gerado",
    "failed": "Falhou",
}

PPE_LABELS = {
    "helmet": "capacete",
    "vest": "colete",
}


def _format_datetime(value) -> str:
    if not value:
        return "n/a"
    if isinstance(value, datetime):
        settings = get_settings()
        local_timezone = _get_local_timezone(settings.timezone_name)
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(local_timezone).strftime("%d/%m/%Y %H:%M:%S")
    return str(value)


def _get_local_timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3))


def _format_decision(value) -> str:
    if not value:
        return "n/a"
    raw = value.value if hasattr(value, "value") else str(value)
    return DECISION_LABELS.get(raw, raw)


def _format_report_kind(value) -> str:
    raw = value.value if hasattr(value, "value") else str(value)
    return REPORT_KIND_LABELS.get(raw, raw)


def _format_report_status(value) -> str:
    raw = value.value if hasattr(value, "value") else str(value)
    return REPORT_STATUS_LABELS.get(raw, raw)


def _format_ppe_list(items: list[str]) -> str:
    if not items:
        return "n/a"
    return ", ".join(PPE_LABELS.get(item, item) for item in items)


def _read_text(path: str | None) -> str | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.read_text(encoding="utf-8")


def _read_bytes(path: str | None) -> bytes | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    return file_path.read_bytes()


def render_camera_form(backend: OnSafeBackend) -> None:
    st.subheader("Cadastro de câmeras")
    source_mode = st.radio(
        "Origem da câmera",
        options=["IP/RTSP", "Webcam do navegador", "Webcam local da máquina"],
        horizontal=True,
    )

    with st.form("camera_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Nome da câmera", placeholder="Portaria")
            if source_mode == "IP/RTSP":
                host = st.text_input("IP ou host", placeholder="192.168.0.10")
                port = st.number_input("Porta", min_value=0, max_value=65535, value=554)
                protocol = st.selectbox("Protocolo", options=[item.value for item in Protocol], index=0)
            elif source_mode == "Webcam local da máquina":
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
                username = st.text_input("Usuário")
                password = st.text_input("Senha", type="password")
                stream_path = st.text_input("Caminho do stream", placeholder="stream1")
            else:
                username = None
                password = None
                stream_path = ""
                st.text_input("Usuário", value="", disabled=True)
                st.text_input("Senha", value="", type="password", disabled=True)
                st.text_input("Caminho do stream", value="", disabled=True)
            required_ppe = st.multiselect("EPIs obrigatórios", options=["helmet", "vest"], default=["helmet", "vest"])
        submitted = st.form_submit_button("Cadastrar câmera")
        if submitted:
            if not name:
                st.error("Informe o nome da câmera.")
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
                    st.success(f"Câmera cadastrada com ID {camera.id}.")
                except ValueError as exc:
                    st.error(str(exc))


def _render_status_badge(health: str) -> str:
    mapping = {
        "online": "ONLINE",
        "offline": "OFFLINE",
        "degraded": "INSTÁVEL",
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
    metric4.metric("Última decisão", _format_decision(status.latest_decision))

    packet = runtime.get_frame()
    if packet is not None:
        st.image(packet.frame, channels="BGR", caption=f"Pré-visualização processada: {_format_datetime(packet.timestamp)}", width=240)

    tracks = runtime.list_active_tracks()
    if tracks:
        st.write("Pessoas rastreadas:")
        for track in tracks:
            st.write(f"- {track.label} | Track {track.track_id} | confirmações {track.stability_hits}")
    with st.expander("Diagnóstico detalhado", expanded=True):
        st.json(status.diagnostics)


def render_browser_camera(backend: OnSafeBackend, camera) -> None:
    st.info("Modo navegador: funciona no Streamlit Cloud e usa a webcam do navegador do usuário.")
    runtime = backend.get_browser_runtime(camera.id)
    st.write(_render_status_badge(runtime.get_status().health.value))

    if webrtc_streamer is None or av is None:
        st.warning("O streamlit-webrtc não está disponível neste ambiente. Usando captura pontual como alternativa.")
        snapshot = st.camera_input("Capturar quadro da webcam", key=f"browser_camera_fallback_{camera.id}")
        if snapshot is not None:
            st.image(snapshot, caption=f"Quadro capturado às {datetime.now().strftime('%H:%M:%S')}")
            st.info("Para análise contínua em nuvem, habilite o streamlit-webrtc nas dependências.")
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
            "A conexão WebRTC ainda não foi estabelecida. Clique em START, escolha a câmera no navegador e aguarde alguns segundos. "
            "Se continuar falhando, a rede pode estar bloqueando a negociação ICE/STUN."
        )
    _render_browser_status(backend, camera.id)
    st.caption("Ao manter o stream ativo, o backend continua analisando os quadros, registrando eventos e gerando relatórios.")


@st.fragment(run_every=2)
def render_network_or_local_camera(backend: OnSafeBackend, camera) -> None:
    status = backend.get_camera_status(camera.id)
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        st.markdown(f"### {camera.name}")
        st.caption(camera.build_stream_url())
        if str(camera.host).strip() == "0":
            st.caption("Fonte local detectada: webcam da máquina que executa o app")
            st.warning(
                "Host 0 funciona apenas quando o app roda localmente na mesma máquina. "
                "No Streamlit Cloud, use a opção Webcam do navegador ou uma câmera IP/RTSP."
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
                latency = f" Latência: {result.latency_ms:.0f} ms" if result.latency_ms is not None else ""
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
    metric4.metric("Última decisão", _format_decision(status.latest_decision))
    if status.status_message:
        st.warning(status.status_message)

    packet = backend.get_live_snapshot(camera.id)
    if packet is not None:
        st.image(packet.frame, channels="BGR", caption=f"Último quadro: {_format_datetime(packet.timestamp)}", width=240)
    else:
        st.info("Ainda não há quadro disponível. Teste a conexão ou inicie o monitoramento.")

    tracks = backend.list_active_tracks(camera.id)
    if tracks:
        st.write("Pessoas rastreadas:")
        for track in tracks:
            st.write(f"- {track.label} | Track {track.track_id} | confirmações {track.stability_hits}")
    with st.expander("Diagnóstico detalhado", expanded=False):
        st.json(status.diagnostics)


def render_monitoring(backend: OnSafeBackend) -> None:
    st.subheader("Monitoramento")
    cameras = backend.list_cameras()
    if not cameras:
        st.info("Cadastre ao menos uma câmera para iniciar os testes no Streamlit.")
        return

    selected_ids = st.multiselect(
        "Câmeras para exibir",
        options=[camera.id for camera in cameras],
        default=[camera.id for camera in cameras[:1]],
        format_func=lambda camera_id: next(camera.name for camera in cameras if camera.id == camera_id),
    )

    selected_cameras = [camera for camera in cameras if camera.id in selected_ids]
    if not selected_cameras:
        st.info("Selecione pelo menos uma câmera para exibir.")
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
                top_left, top_right = st.columns([2, 1])
                with top_left:
                    st.markdown(f"**{event.camera_name}** | {event.person_label}")
                    st.caption(f"Registrado em {_format_datetime(event.created_at)}")
                with top_right:
                    st.markdown(f"**{_format_decision(event.decision_state)}**")
                st.write(
                    f"EPI ausente: {_format_ppe_list(event.missing_ppe)} | "
                    f"Confiança: {event.confidence_score:.2f} | Persistência: {event.persistence_seconds:.1f}s"
                )
                st.caption(event.rationale)
                if event.image_path:
                    image_path = Path(event.image_path)
                    if image_path.exists():
                        st.image(str(image_path), caption="Evidência do evento", width=260)
                    st.code(str(event.image_path), language="text")
    else:
        st.info("Nenhum evento salvo ainda.")

    st.subheader("Relatórios")
    if st.button("Gerar consolidado diário agora"):
        path = backend.build_daily_report()
        st.success(f"Relatório diário gerado em {path}")

    reports = backend.list_reports(limit=20)
    if reports:
        for report in reports:
            with st.container(border=True):
                header_left, header_right = st.columns([2, 1])
                with header_left:
                    st.markdown(f"**{report.title}**")
                    st.caption(f"{_format_report_kind(report.report_kind)} • {_format_datetime(report.created_at)}")
                with header_right:
                    st.markdown(f"**{_format_report_status(report.status)}**")

                download_cols = st.columns(2)
                html_content = _read_text(report.html_path)
                pdf_bytes = _read_bytes(report.pdf_path)

                with download_cols[0]:
                    if html_content and report.html_path:
                        html_name = Path(report.html_path).name
                        st.download_button(
                            "Baixar relatório HTML",
                            data=html_content,
                            file_name=html_name,
                            mime="text/html",
                            key=f"download_html_{report.id}",
                        )
                with download_cols[1]:
                    if pdf_bytes and report.pdf_path:
                        pdf_name = Path(report.pdf_path).name
                        st.download_button(
                            "Baixar relatório PDF",
                            data=pdf_bytes,
                            file_name=pdf_name,
                            mime="application/pdf",
                            key=f"download_pdf_{report.id}",
                        )

                if html_content:
                    with st.expander("Visualizar relatório", expanded=False):
                        components.html(html_content, height=720, scrolling=True)
    else:
        st.info("Nenhum relatório gerado ainda.")


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
    st.caption("Monitoramento de câmeras IP com IA de EPI")
    backend = get_backend()

    render_camera_form(backend)
    st.divider()
    render_monitoring(backend)
    st.divider()
    render_events_and_reports(backend)


if __name__ == "__main__":
    main()
