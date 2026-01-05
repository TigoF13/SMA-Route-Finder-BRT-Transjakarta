# SMA-Based Route Finder for Transjakarta BRT Network

This repository contains a Django-based web application developed as part of an undergraduate thesis in Informatics Engineering.  
The system implements the **Slime Mould Algorithm (SMA)** to determine optimal routes on the **Transjakarta Bus Rapid Transit (BRT)** network using spatial data and user-defined routing preferences.

The project focuses on applying a **metaheuristic optimization approach** to public transportation routing problems and supports experimental evaluation in an academic context.

## 🎯 Research Objectives

This project aims to:

- Model the Transjakarta BRT corridor network as a graph-based spatial system  
- Apply the Slime Mould Algorithm (SMA) for route optimization  
- Analyze the behavior of SMA under different routing preference scenarios  
- Support experimental comparison of routing results for academic research  

## 📌 Key Features

- **SMA-Based Route Optimization**  
  Implements the Slime Mould Algorithm to explore and exploit alternative routes.

- **Graph-Based Network Modeling**  
  Transjakarta corridors are represented as a graph derived from GeoJSON spatial data.

- **Multi-Preference Routing**  
  Routing optimization considers:
  - Distance
  - Number of transfers
  - Route efficiency

- **Experimental Evaluation Support**  
  Generates evaluation logs for analysis and thesis reporting.

## 🗺️ Data Representation

- **Nodes** represent Transjakarta BRT stops  
- **Edges** represent corridor segments between stops  
- **Spatial Data Format**: GeoJSON  
- **Graph Processing**: NetworkX  

## 🧠 Slime Mould Algorithm (SMA) Overview

The Slime Mould Algorithm is a nature-inspired metaheuristic algorithm that mimics the adaptive foraging behavior of slime mould organisms.

In this project:

- Each agent explores possible routes between origin and destination
- Adaptive weights guide exploration and exploitation phases
- Iterative optimization refines route selection based on defined preferences
- The algorithm balances global exploration and local exploitation

## 🚀 Getting Started

### Dependencies

The project was developed and tested using the following environment:

- **Operating System**: Windows 10 / Windows 11  
- **Programming Language**: Python 3.9+  
- **Framework**: Django 4.x  

### Main Libraries

- Django  
- NumPy  
- Pandas  
- GeoPandas  
- NetworkX  
- Shapely  
- Matplotlib 

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/TigoF13/SMA-Route-Finder-BRT-Transjakarta.git
cd SMA-Route-Finder-BRT-Transjakarta
```

### 2. Create and Activate Virtual Environmenty

```bash
py -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database Setup

```bash
py manage.py migrate
```

## ▶️ Executing the Program

### 1. Start Django Development Server

```bash
py manage.py runserver
```

### 2. Access the Application
Open your browser and navigate to:
```text
http://127.0.0.1:8000/
```

## 📊 Experimental Evaluation
Experimental results generated during thesis evaluation are stored in:
```text
evaluation_log_skripsi.xlsx
```
The file contains routing results under different preference scenarios and SMA configurations.

