import os
import numpy as np
import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.collections import LineCollection
import pandas as pd

# ─────────────────────────────────────────────────────────────
# 1. PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="F1 Advanced Telemetry Dashboard", layout="wide")
st.markdown("""
<style>
    button[title="View fullscreen"],
    .stElementToolbar,
    div[data-testid="stElementToolbar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# 2. CACHE FASTF1
# ─────────────────────────────────────────────────────────────
cache_dir = 'cache_f1'
os.makedirs(cache_dir, exist_ok=True)
fastf1.Cache.enable_cache(cache_dir)
fastf1.plotting.setup_mpl()

# ─────────────────────────────────────────────────────────────
# 3. SESSION STATE
# ─────────────────────────────────────────────────────────────
if 'telemetry_data' not in st.session_state:
    st.session_state['telemetry_data'] = None

# ─────────────────────────────────────────────────────────────
# 4. HELPERS
# ─────────────────────────────────────────────────────────────
def format_timedelta(td):
    if pd.isnull(td):
        return "N/A"
    total_seconds = td.total_seconds()
    return f"{int(total_seconds // 60):02d}:{total_seconds % 60:06.3f}"

def lighten_color(color, amount=0.4):
    try:
        c = mcolors.to_rgb(color)
        return mcolors.to_hex(tuple(x + (1 - x) * amount for x in c))
    except Exception:
        return '#FFFFFF'

def darken_color(color, amount=0.5):
    try:
        c = mcolors.to_rgb(color)
        return mcolors.to_hex(tuple(x * amount for x in c))
    except Exception:
        return '#444444'

def apply_plot_styling(ax, s1_distance, s2_distance, total_dist):
    ax.set_xlabel('Distance (m)', fontsize=8)
    ax.xaxis.set_tick_params(labelbottom=True)
    ax.grid(True, linestyle='--', alpha=0.3)
    if s1_distance is not None:
        ax.axvline(s1_distance, color='#555555', linestyle=':', alpha=0.7, linewidth=1.2)
    if s2_distance is not None:
        ax.axvline(s2_distance, color='#555555', linestyle=':', alpha=0.7, linewidth=1.2)
    if None not in (s1_distance, s2_distance) and total_dist:
        s1p, s2p = s1_distance / total_dist, s2_distance / total_dist
        kw = dict(transform=ax.transAxes, color='#888888', fontsize=8, ha='center', fontweight='bold')
        ax.text(s1p / 2,                1.04, "S1", **kw)
        ax.text(s1p + (s2p - s1p) / 2, 1.04, "S2", **kw)
        ax.text(s2p + (1 - s2p) / 2,   1.04, "S3", **kw)

def render_track_map(d):
    """
    Affiche la carte du circuit colorée selon quel pilote est plus rapide
    à chaque point du tracé, en utilisant les données de position GPS.
    """
    try:
        lap_1    = d['lap_1']
        lap_2    = d['lap_2']
        d1, d2   = d['driver_1'], d['driver_2']
        c1, c2   = d['color_1'],  d['color_2']

        # Positions GPS interpolées sur la distance
        pos_1 = lap_1.get_pos_data().add_distance()
        pos_2 = lap_2.get_pos_data().add_distance()

        # Aligner sur une grille de distance commune
        dist_max = min(pos_1['Distance'].max(), pos_2['Distance'].max())
        dist_grid = np.linspace(0, dist_max, 1000)

        x1 = np.interp(dist_grid, pos_1['Distance'], pos_1['X'])
        y1 = np.interp(dist_grid, pos_1['Distance'], pos_1['Y'])

        # Delta de temps interpolé sur la même grille
        delta_interp = np.interp(dist_grid, d['ref_tel']['Distance'], -d['delta_time'])

        # Segments colorés selon qui est plus rapide (delta > 0 → d1 faster)
        points   = np.array([x1, y1]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        faster   = (delta_interp[:-1] > 0).astype(int)  # 1 = d1 faster, 0 = d2 faster

        fig, ax = plt.subplots(figsize=(11, 3.5))
        fig.patch.set_alpha(0)

        # Tracé de base (gris)
        ax.plot(x1, y1, color='#333333', linewidth=6, zorder=1)

        # Segments colorés par pilote
        lc1 = LineCollection(segments[faster == 1], color=c1, linewidth=4, zorder=2)
        lc2 = LineCollection(segments[faster == 0], color=c2, linewidth=4, zorder=2)
        ax.add_collection(lc1)
        ax.add_collection(lc2)

        # Point de départ
        ax.scatter(x1[0], y1[0], color='white', s=80, zorder=5)

        ax.set_aspect('equal')
        ax.axis('off')

        # Légende
        from matplotlib.patches import Patch
        legend_elements = [
            Patch(facecolor=c1, label=f'{d1} faster'),
            Patch(facecolor=c2, label=f'{d2} faster'),
        ]
        ax.legend(handles=legend_elements, loc='lower right', fontsize=9,
                  framealpha=0.3, facecolor='#111111', edgecolor='#444444')

        ax.set_title(f"Track Dominance — {d['grand_prix']} {d['year']}",
                     fontsize=11, color='black', loc='left', pad=8)

        st.pyplot(fig, use_container_width=True)
        plt.close(fig)

    except Exception as e:
        st.warning(f"Track map unavailable: {e}")


def render_charts(d, show_delta, show_speed, show_gear, show_throttle, show_brake, show_rpm):
    """Construit et affiche la figure à partir des données en cache."""
    n = sum([show_delta, show_speed, show_gear, show_throttle, show_brake, show_rpm])
    if n == 0:
        st.error("Please select at least one chart in the sidebar.")
        return
    plt.close('all')
    fig, axes = plt.subplots(n, 1, figsize=(11, 2.8 * n))
    plt.subplots_adjust(hspace=0.65)
    if n == 1:
        axes = [axes]
    skw = dict(s1_distance=d['s1_distance'], s2_distance=d['s2_distance'], total_dist=d['total_dist'])
    d1, d2, c1, c2 = d['driver_1'], d['driver_2'], d['color_1'], d['color_2']
    i = 0

    # 1. Delta — vue macro de l'écart
    if show_delta:
        axes[i].plot(d['ref_tel']['Distance'], -d['delta_time'], color='red', linewidth=1.8)
        axes[i].axhline(0, color='white', linewidth=1.5, alpha=0.5)
        axes[i].fill_between(d['ref_tel']['Distance'], -d['delta_time'], 0,
                             where=(-d['delta_time'] > 0), alpha=0.15, color=c1)
        axes[i].fill_between(d['ref_tel']['Distance'], -d['delta_time'], 0,
                             where=(-d['delta_time'] < 0), alpha=0.15, color=c2)
        axes[i].set_title("TIME DELTA GAP", fontsize=9, color='black', loc='left', pad=10)
        axes[i].set_ylabel(f'▲{d1} | ▼{d2} (s)', fontsize=8, fontweight='bold')
        apply_plot_styling(axes[i], **skw); i += 1

    # 2. Speed
    if show_speed:
        axes[i].plot(d['tel1']['Distance'], d['tel1']['Speed'], label=d1, color=c1, linewidth=1.8)
        axes[i].plot(d['tel2']['Distance'], d['tel2']['Speed'], label=d2, color=c2, linewidth=1.8)
        axes[i].set_title("SPEED (km/h)", fontsize=9, color='black', loc='left', pad=10)
        axes[i].set_ylabel('km/h', fontsize=8, fontweight='bold')
        axes[i].legend(loc='lower left', fontsize=8, framealpha=0.3)
        apply_plot_styling(axes[i], **skw); i += 1

    # 3. Gear — comprendre les points de freinage et accélération
    if show_gear:
        axes[i].plot(d['tel1']['Distance'], d['tel1']['nGear'], label=d1, color=c1, linewidth=1.5, drawstyle='steps-post')
        axes[i].plot(d['tel2']['Distance'], d['tel2']['nGear'], label=d2, color=c2, linewidth=1.5, drawstyle='steps-post')
        axes[i].set_title("GEAR", fontsize=9, color='black', loc='left', pad=10)
        axes[i].set_ylabel('Gear', fontsize=8, fontweight='bold')
        axes[i].set_yticks(range(1, 9))
        axes[i].tick_params(axis='y', labelsize=7)
        axes[i].legend(loc='lower left', fontsize=8, framealpha=0.3)
        apply_plot_styling(axes[i], **skw); i += 1

    # 4. Throttle
    if show_throttle:
        axes[i].plot(d['tel1']['Distance'], d['tel1']['Throttle'], label=d1, color=c1, linewidth=1.8)
        axes[i].plot(d['tel2']['Distance'], d['tel2']['Throttle'], label=d2, color=c2, linewidth=1.8)
        axes[i].set_title("THROTTLE (%)", fontsize=9, color='black', loc='left', pad=10)
        axes[i].set_ylabel('Throttle %', fontsize=8, fontweight='bold')
        apply_plot_styling(axes[i], **skw); i += 1

    # 5. Brake
    if show_brake:
        axes[i].fill_between(d['tel1']['Distance'], d['tel1']['Brake'].astype(int),
                             alpha=0.7, color=c1, label=d1, step='post')
        axes[i].fill_between(d['tel2']['Distance'], d['tel2']['Brake'].astype(int) * -1,
                             alpha=0.7, color=c2, label=d2, step='post')
        axes[i].axhline(0, color='white', linewidth=0.8, alpha=0.4)
        axes[i].set_title("BRAKE (on / off)", fontsize=9, color='black', loc='left', pad=10)
        axes[i].set_ylabel('Brake', fontsize=8, fontweight='bold')
        axes[i].set_yticks([-1, 0, 1])
        axes[i].set_yticklabels([d2, '', d1], fontsize=7)
        axes[i].legend(loc='upper right', fontsize=8, framealpha=0.3)
        apply_plot_styling(axes[i], **skw); i += 1

    # 6. RPM — dernier car le plus "technique"
    if show_rpm:
        axes[i].plot(d['tel1']['Distance'], d['tel1']['RPM'], label=d1, color=c1, linewidth=1.8)
        axes[i].plot(d['tel2']['Distance'], d['tel2']['RPM'], label=d2, color=c2, linewidth=1.8)
        axes[i].set_title("RPM", fontsize=9, color='black', loc='left', pad=10)
        axes[i].set_ylabel('RPM', fontsize=8, fontweight='bold')
        axes[i].legend(loc='lower left', fontsize=8, framealpha=0.3)
        apply_plot_styling(axes[i], **skw)

    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

# ─────────────────────────────────────────────────────────────
# 5. SIDEBAR
# ─────────────────────────────────────────────────────────────
st.sidebar.header("Telemetry Settings")
run_analysis = st.sidebar.button("Calculate & Plot Telemetry", use_container_width=True)
st.sidebar.markdown("---")

year = st.sidebar.selectbox("Season", [2025, 2024, 2023])
gp_list = ['Monaco', 'Spa', 'Monza', 'Silverstone', 'Bahrain', 'Suzuka', 'Austria']
grand_prix = st.sidebar.selectbox("Circuit / Grand Prix", gp_list)

with st.spinner("Fetching available drivers..."):
    try:
        tmp = fastf1.get_session(year, grand_prix, 'Q')
        tmp.load(laps=False, telemetry=False, weather=False)
        drivers_available = sorted([
            f"{r['Abbreviation']} - {r['FullName']}"
            for _, r in tmp.results.iterrows()
        ])
    except Exception:
        drivers_available = ["HAM - Lewis Hamilton", "VER - Max Verstappen", "LEC - Charles Leclerc"]

st.sidebar.markdown("---")
st.sidebar.subheader("Select Drivers")
choice_1 = st.sidebar.selectbox("Driver 1", drivers_available, index=0)
choice_2 = st.sidebar.selectbox("Driver 2", drivers_available, index=1 if len(drivers_available) > 1 else 0)
driver_1 = choice_1.split(" - ")[0]
driver_2 = choice_2.split(" - ")[0]

st.sidebar.markdown("---")
st.sidebar.subheader("Charts to Display")
show_delta    = st.sidebar.checkbox("Time Delta Gap",     value=True)
show_speed    = st.sidebar.checkbox("Car Speed",          value=True)
show_gear     = st.sidebar.checkbox("Gear",               value=False)
show_throttle = st.sidebar.checkbox("Throttle Telemetry", value=True)
show_brake    = st.sidebar.checkbox("Brake (on/off)",     value=False)
show_rpm      = st.sidebar.checkbox("RPM",                value=False)

# ─────────────────────────────────────────────────────────────
# 6. MAIN PAGE
# ─────────────────────────────────────────────────────────────
st.title("F1 Race Engineering & Telemetry Dashboard")
st.write("Advanced trackside analytics tool for telemetry synchronization and sector time breakdown.")

# Re-render depuis le cache à chaque changement de checkbox
if st.session_state['telemetry_data'] is not None and not run_analysis:
    d = st.session_state['telemetry_data']
    st.subheader("Sector Times & Lap Comparison")
    st.table(d['sector_table'])
    render_track_map(d)
    st.markdown("### Live Race Telemetry Traces")
    render_charts(d, show_delta, show_speed, show_gear, show_throttle, show_brake, show_rpm)
    st.stop()

if not run_analysis:
    st.stop()

# ─────────────────────────────────────────────────────────────
# 7. CHARGEMENT DES DONNÉES
# ─────────────────────────────────────────────────────────────
if not any([show_delta, show_speed, show_gear, show_throttle, show_brake, show_rpm]):
    st.error("Please select at least one chart in the sidebar.")
    st.stop()

with st.spinner("Processing telemetry data..."):
    try:
        session = fastf1.get_session(year, grand_prix, 'Q')
        session.load()

        lap_1 = session.laps.pick_driver(driver_1).pick_fastest()
        lap_2 = session.laps.pick_driver(driver_2).pick_fastest()

        tel1 = lap_1.get_car_data().add_distance()
        tel2 = lap_2.get_car_data().add_distance()
        delta_time, ref_tel, _ = fastf1.utils.delta_time(lap_1, lap_2)

        color_1 = fastf1.plotting.get_driver_color(driver_1, session=session)
        color_2 = fastf1.plotting.get_driver_color(driver_2, session=session)
        if color_1 == color_2:
            color_1 = darken_color(color_1, 0.4)
            color_2 = lighten_color(color_2, 0.5)

        tel_c = lap_1.get_telemetry().add_distance()
        s1_mask = tel_c['Time'] >= lap_1['Sector1Time']
        s2_mask = tel_c['Time'] >= lap_1['Sector1Time'] + lap_1['Sector2Time']
        s1_distance = tel_c.loc[s1_mask, 'Distance'].iloc[0] if s1_mask.any() else None
        s2_distance = tel_c.loc[s2_mask, 'Distance'].iloc[0] if s2_mask.any() else None
        total_dist  = tel1['Distance'].max()

        sector_table = pd.DataFrame({
            "Metric":  ["Sector 1", "Sector 2", "Sector 3", "Total Lap Time"],
            driver_1: [format_timedelta(lap_1['Sector1Time']), format_timedelta(lap_1['Sector2Time']),
                       format_timedelta(lap_1['Sector3Time']), format_timedelta(lap_1['LapTime'])],
            driver_2: [format_timedelta(lap_2['Sector1Time']), format_timedelta(lap_2['Sector2Time']),
                       format_timedelta(lap_2['Sector3Time']), format_timedelta(lap_2['LapTime'])],
        })

        st.session_state['telemetry_data'] = {
            'tel1': tel1, 'tel2': tel2,
            'ref_tel': ref_tel, 'delta_time': delta_time,
            'color_1': color_1, 'color_2': color_2,
            'driver_1': driver_1, 'driver_2': driver_2,
            's1_distance': s1_distance, 's2_distance': s2_distance,
            'total_dist': total_dist,
            'sector_table': sector_table,
            'lap_1': lap_1, 'lap_2': lap_2,
            'grand_prix': grand_prix, 'year': year,
        }

        d = st.session_state['telemetry_data']
        st.subheader("Sector Times & Lap Comparison")
        st.table(sector_table)
        render_track_map(d)
        st.markdown("### Live Race Telemetry Traces")
        render_charts(d, show_delta, show_speed, show_gear, show_throttle, show_brake, show_rpm)
        st.success("Analysis generated successfully!")

    except Exception as e:
        st.error(f"An error occurred while fetching the data. Details: {e}")
