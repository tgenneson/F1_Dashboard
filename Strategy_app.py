import os
import streamlit as st
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.colors as mcolors

# 1. Streamlit Web Page Configuration
st.set_page_config(page_title="F1 Race Strategy Analytics", layout="wide")
st.title("F1 Race Pace & Strategy Analyzer")
st.write("Trackside performance tool for multi-stint race pace evolution and tire degradation mapping.")

# 2. Automatic Cache Management
cache_dir = 'cache_f1'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir)
fastf1.plotting.setup_mpl()

# Professional engineering dark theme customization
plt.rcParams['figure.facecolor'] = '#0E1117'
plt.rcParams['axes.facecolor'] = '#151922'
plt.rcParams['axes.edgecolor'] = '#333333'
plt.rcParams['grid.color'] = '#222222'
plt.rcParams['xtick.color'] = '#888888'
plt.rcParams['ytick.color'] = '#888888'

# Hide redundant Streamlit interactive elements
st.markdown(
    """
    <style>
        button[title="View fullscreen"], .stElementToolbar, div[data-testid="stElementToolbar"] {
            display: none !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# 3. Sidebar Configuration
st.sidebar.header("Race Parameters")
run_strategy = st.sidebar.button("Run Strategy Analysis")
st.sidebar.markdown("---")

year = st.sidebar.selectbox("Season", [2025, 2024, 2023])
gp_list = ['Spa', 'Monza', 'Silverstone', 'Monaco', 'Bahrain', 'Suzuka', 'Austria']
grand_prix = st.sidebar.selectbox("Grand Prix", gp_list)

# Background driver list loading
with st.spinner("Fetching driver grid..."):
    try:
        temp_session = fastf1.get_session(year, grand_prix, 'R')
        temp_session.load(laps=True, telemetry=False, weather=False)
        drivers_available = [f"{row['Abbreviation']} - {row['FullName']}" for index, row in temp_session.results.iterrows()]
        drivers_available.sort()
    except Exception:
        drivers_available = ["VER - Max Verstappen", "HAM - Lewis Hamilton", "LEC - Charles Leclerc", "NOR - Lando Norris"]

st.sidebar.markdown("---")
st.sidebar.subheader("Select Drivers")
choice_1 = st.sidebar.selectbox("Driver 1 (Reference)", drivers_available, index=0)
choice_2 = st.sidebar.selectbox("Driver 2 (Target)", drivers_available, index=1 if len(drivers_available) > 1 else 0)

driver_1 = choice_1.split(" - ")[0]
driver_2 = choice_2.split(" - ")[0]

# Helper function to convert timedelta to a clean MM:SS.mmm string
def format_timedelta(td):
    if pd.isnull(td): return "N/A"
    total_seconds = td.total_seconds()
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:06.3f}"

# Helper function to generate distinct teammate colors
def lighten_color(color, amount=0.4):
    try:
        c = mcolors.to_rgb(color)
        return mcolors.to_hex((c[0] + (1 - c[0]) * amount, c[1] + (1 - c[1]) * amount, c[2] + (1 - c[2]) * amount))
    except Exception:
        return '#FFFFFF'

def darken_color(color, amount=0.5):
    try:
        c = mcolors.to_rgb(color)
        return mcolors.to_hex((c[0] * amount, c[1] * amount, c[2] * amount))
    except Exception:
        return '#444444'

# 4. Processing Analysis when Button is Clicked
if run_strategy:
    with st.spinner("Processing stint summaries and clearing out anomalies..."):
        try:
            session = fastf1.get_session(year, grand_prix, 'R')
            session.load(telemetry=False, weather=False)

            laps_1 = session.laps.pick_driver(driver_1)
            laps_2 = session.laps.pick_driver(driver_2)

            # Filter out Safety Car laps, VSC laps, and heavy pit-lane deltas (Outliers > 107% of median lap)
            median_lap = laps_1['LapTime'].median().total_seconds()
            clean_laps_1 = laps_1[laps_1['LapTime'].dt.total_seconds() < (median_lap * 1.07)]
            clean_laps_2 = laps_2[laps_2['LapTime'].dt.total_seconds() < (median_lap * 1.07)]

            # --- Stint Summary Section ---
            st.subheader("Stint Management & Compound History")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{driver_1} Stint Data**")
                stint_df1 = laps_1.groupby(['Stint', 'Compound']).agg({
                    'LapNumber': 'count',
                    'TyreLife': 'max'
                }).rename(columns={'LapNumber': 'Laps in Stint', 'TyreLife': 'Max Tyre Age'})
                st.table(stint_df1)
                
            with col2:
                st.markdown(f"**{driver_2} Stint Data**")
                stint_df2 = laps_2.groupby(['Stint', 'Compound']).agg({
                    'LapNumber': 'count',
                    'TyreLife': 'max'
                }).rename(columns={'LapNumber': 'Laps in Stint', 'TyreLife': 'Max Tyre Age'})
                st.table(stint_df2)

            # --- Race Engineering Statistics ---
            st.markdown("<hr style='border: 1px solid #333333; margin: 25px 0;' />", unsafe_allow_html=True)
            st.subheader("Race Performance Metrics")
            
            stats_data = {
                "Metric": ["Total Laps Covered", "Median Lap Time", "Fastest Lap Time", "Estimated Pit Stop Loss"],
                driver_1: [
                    len(laps_1),
                    format_timedelta(laps_1['LapTime'].median()),
                    format_timedelta(laps_1['LapTime'].min()),
                    f"{laps_1[laps_1['PitOutTime'].notnull()]['LapNumber'].count()} Stop(s)"
                ],
                driver_2: [
                    len(laps_2),
                    format_timedelta(laps_2['LapTime'].median()),
                    format_timedelta(laps_2['LapTime'].min()),
                    f"{laps_2[laps_2['PitOutTime'].notnull()]['LapNumber'].count()} Stop(s)"
                ]
            }
            st.table(pd.DataFrame(stats_data))

            # --- Main Plot Generation ---
            st.markdown("<hr style='border: 1px solid #333333; margin: 25px 0;' />", unsafe_allow_html=True)
            st.subheader("Race Pace Evolution & Degradation Profiles")
            
            fig, ax = plt.subplots(figsize=(12, 6.5))

            # Resolve team color duplicates
            color_1 = fastf1.plotting.get_driver_color(driver_1, session=session)
            color_2 = fastf1.plotting.get_driver_color(driver_2, session=session)
            if color_1 == color_2:
                color_1 = darken_color(color_1, amount=0.5)
                color_2 = lighten_color(color_2, amount=0.5)

            # Plot main lines
            ax.plot(clean_laps_1['LapNumber'], clean_laps_1['LapTime'].dt.total_seconds(), 
                    label=f"{driver_1} Pace Profile", color=color_1, marker='o', markersize=3, linewidth=1.5)
            
            ax.plot(clean_laps_2['LapNumber'], clean_laps_2['LapTime'].dt.total_seconds(), 
                    label=f"{driver_2} Pace Profile", color=color_2, marker='s', markersize=3, linewidth=1.5)

            # Highlight Pit Stop event horizons
            pit_stops_1 = laps_1[laps_1['PitOutTime'].notnull()]['LapNumber'].tolist()
            for idx, lap in enumerate(pit_stops_1):
                ax.axvline(lap, color=color_1, linestyle='--', alpha=0.5, 
                           label=f"{driver_1} Pit Event" if idx == 0 else "")
                ax.text(lap + 0.3, ax.get_ylim()[0] + (ax.get_ylim()[1]-ax.get_ylim()[0])*0.1, 
                        f"BOX L{lap}", color=color_1, fontsize=8, rotation=90, fontweight='bold')

            pit_stops_2 = laps_2[laps_2['PitOutTime'].notnull()]['LapNumber'].tolist()
            for idx, lap in enumerate(pit_stops_2):
                ax.axvline(lap, color=color_2, linestyle=':', alpha=0.5, 
                           label=f"{driver_2} Pit Event" if idx == 0 else "")
                ax.text(lap - 1.2, ax.get_ylim()[0] + (ax.get_ylim()[1]-ax.get_ylim()[0])*0.1, 
                        f"BOX L{lap}", color=color_2, fontsize=8, rotation=90, fontweight='bold')

            # Formatting chart labels and grids
            ax.set_xlabel("Lap Number", color='#888888', fontsize=10, labelpad=10)
            ax.set_ylabel("Lap Time (Minutes:Seconds)", color='#888888', fontsize=10, labelpad=10)
            ax.grid(True, linestyle=':', alpha=0.3)
            
            # Legendary telemetry output format for Y axis
            def seconds_formatter(x, pos):
                return f"{int(x // 60)}:{int(x % 60):02d}"
            ax.yaxis.set_major_formatter(plt.FuncFormatter(seconds_formatter))

            # Render polished legend box
            ax.legend(loc='upper right', facecolor='#151922', edgecolor='#333333', 
                      fontsize=9, labelcolor='white', framealpha=0.9)

            st.pyplot(fig)
            st.success("Analysis generated successfully under FIA engineering regulations.")

        except Exception as e:
            st.error(f"Strategy processing halted due to: {e}")
