import React from 'react';
import Plot from 'react-plotly.js';

const ChartViewer = ({ data, plotType }) => {
  if (!data || data.length === 0) return null;

  // Filter out rows where temp or salinity is null
  const validData = data.filter(d => d.temperature !== null && d.salinity !== null);

  // Group by float_id + cycle_number
  const groups = {};
  validData.forEach(row => {
    const key = `${row.float_id} (Cycle ${row.cycle_number})`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(row);
  });

  const generateDepthProfile = () => {
    const traces = [];
    
    // Create a trace for each profile
    Object.keys(groups).forEach(key => {
      const profileData = groups[key].sort((a, b) => a.depth_m - b.depth_m);
      
      // Temperature
      traces.push({
        x: profileData.map(d => d.temperature),
        y: profileData.map(d => d.depth_m),
        type: 'scatter',
        mode: 'lines+markers',
        name: `${key} - Temp`,
        xaxis: 'x',
        yaxis: 'y',
        line: { width: 2 },
        marker: { size: 4 }
      });
      
      // Salinity
      traces.push({
        x: profileData.map(d => d.salinity),
        y: profileData.map(d => d.depth_m),
        type: 'scatter',
        mode: 'lines+markers',
        name: `${key} - Salinity`,
        xaxis: 'x2',
        yaxis: 'y',
        line: { width: 2, dash: 'dot' },
        marker: { size: 4 }
      });
    });

    return {
      data: traces,
      layout: {
        title: 'Depth Profile (Temperature & Salinity)',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f8fafc' },
        hovermode: 'closest',
        showlegend: true,
        legend: { x: 1.1, y: 1 },
        yaxis: {
          title: 'Depth (m)',
          autorange: 'reversed', // Deepest at bottom
          gridcolor: 'rgba(255,255,255,0.1)'
        },
        xaxis: {
          title: 'Temperature (°C)',
          gridcolor: 'rgba(255,255,255,0.1)',
          domain: [0, 0.45]
        },
        xaxis2: {
          title: 'Salinity (psu)',
          gridcolor: 'rgba(255,255,255,0.1)',
          domain: [0.55, 1]
        }
      }
    };
  };

  const generateTimeSeries = () => {
    // For time series, we might just plot the surface or average temperature over time
    // Let's just group by float_id for time series across the dataset
    const floats = {};
    validData.forEach(row => {
      if (!floats[row.float_id]) floats[row.float_id] = [];
      floats[row.float_id].push(row);
    });

    const traces = [];
    Object.keys(floats).forEach(floatId => {
      // Sort by time
      const floatData = floats[floatId].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
      
      traces.push({
        x: floatData.map(d => d.timestamp),
        y: floatData.map(d => d.temperature),
        type: 'scatter',
        mode: 'markers',
        name: `Float ${floatId} - Temp`,
        marker: { size: 6, opacity: 0.7 }
      });
    });

    return {
      data: traces,
      layout: {
        title: 'Temperature over Time',
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f8fafc' },
        xaxis: { title: 'Date', gridcolor: 'rgba(255,255,255,0.1)' },
        yaxis: { title: 'Temperature (°C)', gridcolor: 'rgba(255,255,255,0.1)' }
      }
    };
  };

  const chart = plotType === 'time_series' ? generateTimeSeries() : generateDepthProfile();

  return (
    <div className="chart-wrapper">
      <Plot
        data={chart.data}
        layout={{...chart.layout, autosize: true}}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
        config={{ displayModeBar: true, responsive: true }}
      />
    </div>
  );
};

export default ChartViewer;
