from __future__ import annotations

from typing import Iterable

import streamlit as st

from app.core.config import get_settings
from app.core.enums import Protocol
from app.core.schemas import CameraConfig
from app.integrations.streamlit_contracts import OnSafeBackend


@st.cache_resource
def get_backend() -> OnSafeBackend:
    settings = get_settings()
    return OnSafeBackend(settings)


def render_camera_form(backend: OnSafeBackend) -> None:
    st.subheader("Cadastro de cameras")
    with st.form("camera_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Nome da camera", placeholder="Portaria")
            host = st.text_input("IP ou host", placeholder="192.168.0.10 ou 0 para webcam local")
            port = st.number_input("Porta", min_value=1, max_value=65535, value=554)
            protocol = st.selectbox("Protocolo", options=[item.value for item in Protocol], index=0)
        with col2:
            username = st.text_input("Usuario")
            password = st.text_input("Senha", type="password")
            stream_path = st.text_input("Caminho do stream", placeholder="stream1")
            required_ppe = st.multiselect("EPIs obrigatorios", options=["helmet", "vest"], default=["helmet", "vest"])
        submitted = st.form_submit_button("Cadastrar camera")
        if submitted:
            if not name or not host:
                st.error("Informe ao menos nome e host da camera.")
            else:
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


def _render_status_badge(health: str) -> str:
    mapping = {
        "online": "🟢 ONLINE",
        "offline": "🔴 OFFLINE",
        "degraded": "🟠 INSTAVEL",
        "starting": "🟡 INICIANDO",
        "stopped": "⚪ PARADA",
    }
    return mapping.get(health, health.upper())


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

    for camera in cameras:
        with st.container(border=True):
            status = backend.get_camera_status(camera.id)
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                st.markdown(f"### {camera.name}")
                st.caption(camera.build_stream_url())
                if str(camera.host).strip() == "0":
                    st.caption("Fonte local detectada: webcam do notebook")
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
                        st.success(f"{result.message} Latencia: {result.latency_ms:.0f} ms")
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

            if camera.id in selected_ids:
                packet = backend.get_live_snapshot(camera.id)
                if packet is not None:
                    st.image(packet.frame, channels="BGR", caption=f"Ultimo frame: {packet.timestamp}")
                else:
                    st.info("Sem frame disponivel ainda. Teste a conexao ou inicie o monitoramento.")

                tracks = backend.list_active_tracks(camera.id)
                if tracks:
                    st.write("Pessoas rastreadas:")
                    for track in tracks:
                        st.write(f"- {track.label} | Track {track.track_id} | hits {track.stability_hits}")


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
