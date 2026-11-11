import os
import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt

# 1. Configuration des graphiques
fastf1.plotting.setup_mpl()

# 2. Gestion du dossier Cache
cache_dir = 'cache_f1'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
fastf1.Cache.enable_cache(cache_dir) 

def analyser_performance_pilotes():
    print("Step 1: Connexion aux serveurs de la F1...")
    session = fastf1.get_session(2024, 'Monaco', 'Q')
    
    print("Step 2: Téléchargement de la session globale (Monaco 2024)...")
    print("--> Attention: cette étape prend entre 1 et 4 minutes la première fois !")
    session.load()
    
    print("Step 3: Extraction du meilleur tour de Hamilton et Verstappen...")
    lap_ham = session.laps.pick_driver('HAM').pick_fastest()
    lap_ver = session.laps.pick_driver('VER').pick_fastest()

    print("Step 4: Synchronisation des données de télémétrie...")
    telemetry_ham = lap_ham.get_car_data().add_distance()
    telemetry_ver = lap_ver.get_car_data().add_distance()

    print("Step 5: Génération des graphiques de performance...")
    fig, ax = plt.subplots(3, 1, figsize=(12, 10), sharex=True)
    fig.suptitle("Mercedes (HAM) vs Red Bull (VER) - Monaco (Meilleur Tour)", fontsize=16)

    # Vitesse
    ax[0].plot(telemetry_ham['Distance'], telemetry_ham['Speed'], label='Hamilton (Mercedes)', color='#00A19B') 
    ax[0].plot(telemetry_ver['Distance'], telemetry_ver['Speed'], label='Verstappen (Red Bull)', color='#FCD561') 
    ax[0].set_ylabel('Vitesse (km/h)')
    ax[0].legend(loc='lower left')
    ax[0].grid(True, linestyle='--', alpha=0.5)

    # Accélérateur
    ax[1].plot(telemetry_ham['Distance'], telemetry_ham['Throttle'], color='#00A19B')
    ax[1].plot(telemetry_ver['Distance'], telemetry_ver['Throttle'], color='#FCD561')
    ax[1].set_ylabel('Accélérateur (%)')
    ax[1].grid(True, linestyle='--', alpha=0.5)

    # Frein
    ax[2].plot(telemetry_ham['Distance'], telemetry_ham['Brake'] * 100, color='#00A19B')
    ax[2].plot(telemetry_ver['Distance'], telemetry_ver['Brake'] * 100, color='#FCD561')
    ax[2].set_ylabel('Frein (0 à 100%)')
    ax[2].set_xlabel('Distance parcourue sur le circuit (m)')
    ax[2].grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig('comparaison_performance_f1.png', dpi=300)
    
    print("Step 6: Affichage du graphique final !")
    plt.show()

if __name__ == "__main__":
    analyser_performance_pilotes()
