import React from 'react';
import Plot from 'react-plotly.js';

const ChartViewer = ({ data, plotType = 'depth_profile', parameter = 'all' }) => {
  if (!data || data.length === 0) {
    return (
      <div className="empty-state">
        <h3>No observation data to plot</h3>
        <p>Run a query to generate scientific depth profiles and ocean trends.</p>
      </div>
    );
  }

  const validData = data.filter(d => d.depth_m !== null);

  // Group data by profile (float_id + cycle_number)
  const profilesMap = {};
  validData.forEach(row => {
    const key = `Float ${row.float_id} (Cycle ${row.cycle_number || 1})`;
    if (!profilesMap[key]) profilesMap[key] = [];
    profilesMap[key].push(row);
  });

  // 1. Depth Profile Plot (Respects requested parameter)
  const generateDepthProfile = () => {
    const traces = [];
    const keys = Object.keys(profilesMap).slice(0, 15); // limit to 15 profiles for visual clarity

    const showTemp = parameter === 'all' || parameter === 'temperature';
    const showSal = parameter === 'all' || parameter === 'salinity';
    const dualAxis = showTemp && showSal;

    keys.forEach((key) => {
      const profRows = profilesMap[key].sort((a, b) => a.depth_m - b.depth_m);
      
      // Temperature trace
      if (showTemp) {
        const tempRows = profRows.filter(r => r.temperature !== null);
        if (tempRows.length > 0) {
          traces.push({
            x: tempRows.map(d => d.temperature),
            y: tempRows.map(d => d.depth_m),
            type: 'scatter',
            mode: 'lines+markers',
            name: `${key} - Temp`,
            xaxis: dualAxis ? 'x' : 'x',
            yaxis: 'y',
            line: { width: 2 },
            marker: { size: 4 }
          });
        }
      }

      // Salinity trace
      if (showSal) {
        const salRows = profRows.filter(r => r.salinity !== null);
        if (salRows.length > 0) {
          traces.push({
            x: salRows.map(d => d.salinity),
            y: salRows.map(d => d.depth_m),
            type: 'scatter',
            mode: 'lines+markers',
            name: `${key} - Salinity`,
            xaxis: dualAxis ? 'x2' : 'x',
            yaxis: 'y',
            line: { width: 2, dash: showTemp ? 'dot' : 'solid' },
            marker: { size: 4 }
          });
        }
      }
    });

    // Build axis labels based on what's shown
    const singleLabel = showTemp ? 'Temperature (°C)' : 'Practical Salinity (psu)';
    const titleText = showTemp && !showSal ? 'Temperature Depth Profiles'
      : showSal && !showTemp ? 'Salinity Depth Profiles'
      : 'ARGO Vertical Depth Profiles';

    const layout = {
      title: { text: titleText, font: { color: '#06b6d4', size: 16 } },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(5,9,20,0.8)',
      font: { color: '#94a3b8' },
      hovermode: 'closest',
      showlegend: true,
      legend: { font: { color: '#f8fafc', size: 10 }, orientation: 'h', y: -0.2 },
      yaxis: {
        title: 'Derived Depth (m)',
        autorange: 'reversed',
        gridcolor: 'rgba(255,255,255,0.08)',
        zerolinecolor: 'rgba(255,255,255,0.1)'
      },
      xaxis: {
        title: dualAxis ? 'Temperature (°C)' : singleLabel,
        gridcolor: 'rgba(255,255,255,0.08)',
        domain: dualAxis ? [0, 0.46] : [0, 1]
      },
    };

    if (dualAxis) {
      layout.xaxis2 = {
        title: 'Practical Salinity (psu)',
        gridcolor: 'rgba(255,255,255,0.08)',
        domain: [0.54, 1]
      };
    }

    return { data: traces, layout };
  };

  // 2. Temporal Trend Plot (Scientifically aggregated by observation date to avoid depth-smearing)
  const generateTimeSeries = () => {
    // If entire water column is present, isolate surface layer (0-200m) to avoid mixing depth levels into one time series.
    // If data is already depth-filtered (e.g. at 500m), use all available depth rows.
    const hasDeepDataOnly = validData.every(d => d.depth_m > 200);
    const targetRows = hasDeepDataOnly ? validData : validData.filter(d => d.depth_m <= 200);

    const showTemp = parameter === 'all' || parameter === 'temperature';
    const showSal = parameter === 'all' || parameter === 'salinity';
    
    // Group by timestamp date
    const dateMap = {};
    targetRows.forEach(r => {
      if (!r.timestamp) return;
      const dateKey = r.timestamp.slice(0, 10);
      if (!dateMap[dateKey]) dateMap[dateKey] = { temps: [], sals: [] };
      if (r.temperature !== null) dateMap[dateKey].temps.push(r.temperature);
      if (r.salinity !== null) dateMap[dateKey].sals.push(r.salinity);
    });

    const dates = Object.keys(dateMap).sort();
    const meanTemps = dates.map(d => dateMap[d].temps.length ? (dateMap[d].temps.reduce((a,b) => a+b, 0) / dateMap[d].temps.length) : null);
    const meanSals = dates.map(d => dateMap[d].sals.length ? (dateMap[d].sals.reduce((a,b) => a+b, 0) / dateMap[d].sals.length) : null);

    const traces = [];
    const isDual = showTemp && showSal;

    if (showTemp) {
      const validTempPoints = dates.map((d, i) => ({ x: d, y: meanTemps[i] })).filter(p => p.y !== null);
      if (validTempPoints.length > 0) {
        traces.push({
          x: validTempPoints.map(p => p.x),
          y: validTempPoints.map(p => p.y),
          type: 'scatter',
          mode: 'lines+markers',
          name: isDual ? 'Mean Temp (°C)' : 'Temperature (°C)',
          line: { color: '#38bdf8', width: 3 },
          marker: { size: 7 }
        });
      }
    }

    if (showSal) {
      const validSalPoints = dates.map((d, i) => ({ x: d, y: meanSals[i] })).filter(p => p.y !== null);
      if (validSalPoints.length > 0) {
        traces.push({
          x: validSalPoints.map(p => p.x),
          y: validSalPoints.map(p => p.y),
          type: 'scatter',
          mode: 'lines+markers',
          name: isDual ? 'Mean Salinity (psu)' : 'Salinity (psu)',
          yaxis: isDual ? 'y2' : 'y',
          line: { color: '#10b981', width: isDual ? 2 : 3, dash: isDual ? 'dash' : 'solid' },
          marker: { size: isDual ? 6 : 7 }
        });
      }
    }

    const depthNote = hasDeepDataOnly ? 'Target Depth Layer' : 'Upper Ocean Layer (0–200m)';
    const titleParam = showTemp && !showSal ? 'Temperature' : showSal && !showTemp ? 'Salinity' : 'Ocean';

    const layout = {
      title: { text: `${titleParam} Temporal Trend (${depthNote})`, font: { color: '#06b6d4', size: 16 } },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(5,9,20,0.8)',
      font: { color: '#94a3b8' },
      xaxis: { title: 'Observation Date', gridcolor: 'rgba(255,255,255,0.08)' },
      yaxis: { 
        title: showTemp ? 'Temperature (°C)' : 'Practical Salinity (psu)', 
        gridcolor: 'rgba(255,255,255,0.08)' 
      },
      legend: { orientation: 'h', y: 1.15 }
    };

    if (isDual) {
      layout.yaxis2 = {
        title: 'Salinity (psu)',
        overlaying: 'y',
        side: 'right',
        gridcolor: 'rgba(255,255,255,0.05)'
      };
    }

    return { data: traces, layout };
  };

  // 3. T-S Diagram (Temperature vs Salinity Scatter with Depth Encoding)
  const generateScatterTS = () => {
    const tsRows = validData.filter(d => d.temperature !== null && d.salinity !== null);

    const trace = {
      x: tsRows.map(d => d.salinity),
      y: tsRows.map(d => d.temperature),
      mode: 'markers',
      type: 'scatter',
      text: tsRows.map(d => `Float ${d.float_id} | Depth: ${d.depth_m}m`),
      marker: {
        size: 6,
        color: tsRows.map(d => d.depth_m),
        colorscale: 'Viridis',
        reversescale: true,
        colorbar: { title: 'Depth (m)', titlefont: { color: '#f8fafc' }, tickfont: { color: '#94a3b8' } }
      }
    };

    return {
      data: [trace],
      layout: {
        title: { text: 'Temperature–Salinity (T-S) Diagram', font: { color: '#06b6d4', size: 16 } },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(5,9,20,0.8)',
        font: { color: '#94a3b8' },
        xaxis: { title: 'Practical Salinity (psu)', gridcolor: 'rgba(255,255,255,0.08)' },
        yaxis: { title: 'In-Situ Temperature (°C)', gridcolor: 'rgba(255,255,255,0.08)' }
      }
    };
  };

  const chart = plotType === 'time_series' 
    ? generateTimeSeries() 
    : plotType === 'scatter' 
    ? generateScatterTS() 
    : generateDepthProfile();

  return (
    <div style={{ width: '100%', height: '100%', padding: '1rem' }}>
      <Plot
        data={chart.data}
        layout={{ ...chart.layout, autosize: true }}
        style={{ width: '100%', height: '100%' }}
        useResizeHandler={true}
        config={{ displayModeBar: true, responsive: true }}
      />
    </div>
  );
};

export default ChartViewer;

