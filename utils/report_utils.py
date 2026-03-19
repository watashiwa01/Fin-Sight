import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from config import OUTPUT_DIR

def generate_report_charts(output_dir=OUTPUT_DIR):
    """
    Generates Radar and Line charts for reports to match the UI.
    Returns: dict with paths to generated images.
    """
    charts = {}
    
    # 1. Radar Chart (Pillar Comparison)
    categories = ['Character', 'Capacity', 'Capital', 'Collateral', 'Conditions']
    values = [85, 70, 78, 92, 65]
    
    label_loc = np.linspace(start=0, stop=2 * np.pi, num=len(values), endpoint=False)
    
    plt.figure(figsize=(6, 6), dpi=100)
    plt.subplot(polar=True)
    plt.plot(label_loc, values, label='Applicant', color='#3b82f6', linewidth=2)
    plt.fill(label_loc, values, color='#3b82f6', alpha=0.25)
    plt.thetagrids(np.degrees(label_loc), categories)
    plt.title('Five Cs Pillar Comparison', size=15, color='#1e293b', y=1.1)
    
    radar_path = output_dir / "report_radar.png"
    plt.savefig(radar_path, bbox_inches='tight')
    plt.close()
    charts['radar'] = str(radar_path)
    
    # 2. Line Chart (Financial Trends)
    years = ['FY21', 'FY22', 'FY23', 'FY24 (Est)']
    revenue = [18.2, 22.5, 28.5, 32.1]
    profit = [2.1, 3.4, 4.2, 5.1]
    
    plt.figure(figsize=(8, 4), dpi=100)
    plt.plot(years, revenue, marker='o', label='Revenue (Cr)', color='#3b82f6', linewidth=3)
    plt.plot(years, profit, marker='s', label='Net Profit (Cr)', color='#10b981', linewidth=3)
    plt.fill_between(years, revenue, color='#3b82f6', alpha=0.1)
    plt.fill_between(years, profit, color='#10b981', alpha=0.1)
    plt.title('Financial Performance Trends', size=14, color='#1e293b')
    plt.legend()
    plt.grid(True, linestyle='--', alpha=0.3)
    
    line_path = output_dir / "report_trends.png"
    plt.savefig(line_path, bbox_inches='tight')
    plt.close()
    charts['trends'] = str(line_path)
    
    return charts
