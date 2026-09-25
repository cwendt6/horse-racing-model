import React, { useState } from 'react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ScatterChart, Scatter, Cell } from 'recharts';

const PaceVisualizationDashboard = () => {
  // Sample data - replace with your actual race data
  const [selectedRace, setSelectedRace] = useState(1);
  
  // Sample race data structure
  const raceData = {
    1: {
      raceNumber: 1,
      distance: '6F',
      surface: 'Dirt',
      paceScenario: 'fast_pace',
      horses: [
        { name: 'Quick Speed', style: 'E', paceScore: 45, beyer: 89, post: 2, color: '#ef4444' },
        { name: 'Presser Pro', style: 'EP', paceScore: 68, beyer: 85, post: 5, color: '#f97316' },
        { name: 'Mid Pack', style: 'P', paceScore: 75, beyer: 83, post: 3, color: '#eab308' },
        { name: 'Late Closer', style: 'S', paceScore: 85, beyer: 87, post: 7, color: '#22c55e' },
        { name: 'Another EP', style: 'EP', paceScore: 52, beyer: 78, post: 1, color: '#f97316' },
        { name: 'Stalker', style: 'P', paceScore: 72, beyer: 81, post: 4, color: '#eab308' }
      ]
    }
  };
  
  const race = raceData[selectedRace];
  
  // Projected race positions through the race
  const paceProfile = race.horses.map(horse => {
    const startPos = horse.style === 'E' ? 1 : 
                     horse.style === 'EP' ? 3 :
                     horse.style === 'P' ? 6 : 9;
    
    return {
      horse: horse.name,
      start: startPos,
      firstCall: startPos + (Math.random() * 2 - 1),
      secondCall: horse.style === 'S' ? startPos - 2 : startPos + (Math.random() * 1),
      stretch: horse.style === 'S' ? startPos - 3 : startPos + (Math.random() * 1),
      finish: startPos + (100 - horse.paceScore) / 20,
      color: horse.color
    };
  });
  
  // Transform for line chart
  const lineChartData = [
    {
      call: 'Start',
      ...Object.fromEntries(race.horses.map(h => [h.name, paceProfile.find(p => p.horse === h.name).start]))
    },
    {
      call: '1st Call',
      ...Object.fromEntries(race.horses.map(h => [h.name, paceProfile.find(p => p.horse === h.name).firstCall]))
    },
    {
      call: '2nd Call',
      ...Object.fromEntries(race.horses.map(h => [h.name, paceProfile.find(p => p.horse === h.name).secondCall]))
    },
    {
      call: 'Stretch',
      ...Object.fromEntries(race.horses.map(h => [h.name, paceProfile.find(p => p.horse === h.name).stretch]))
    },
    {
      call: 'Finish',
      ...Object.fromEntries(race.horses.map(h => [h.name, paceProfile.find(p => p.horse === h.name).finish]))
    }
  ];
  
  // Pace fit bar chart data
  const paceFitData = race.horses.map(h => ({
    name: h.name,
    score: h.paceScore,
    fill: h.color
  })).sort((a, b) => b.score - a.score);
  
  // Speed vs Pace scatter
  const scatterData = race.horses.map(h => ({
    x: h.beyer,
    y: h.paceScore,
    name: h.name,
    fill: h.color
  }));
  
  // Pace scenario descriptions
  const paceDescriptions = {
    fast_pace: {
      title: '🔥 Fast Pace Expected',
      description: 'Multiple early speed types will duel. Early speed vulnerable, closers favored.',
      color: 'bg-red-100 border-red-300 text-red-800'
    },
    moderate_pace: {
      title: '⚖️ Moderate Pace Expected',
      description: 'Honest pace with some early pressure. All running styles competitive.',
      color: 'bg-yellow-100 border-yellow-300 text-yellow-800'
    },
    slow_pace: {
      title: '🐢 Slow Pace Expected',
      description: 'Limited early speed. Front runners dominate, closers struggle.',
      color: 'bg-blue-100 border-blue-300 text-blue-800'
    }
  };
  
  const currentPace = paceDescriptions[race.paceScenario];
  
  return (
    <div className="w-full max-w-7xl mx-auto p-6 bg-gray-50">
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">
          Race {race.raceNumber} Pace Analysis
        </h1>
        <div className="flex gap-4 text-sm text-gray-600">
          <span>📏 {race.distance}</span>
          <span>🏇 {race.surface}</span>
          <span>👥 {race.horses.length} Horses</span>
        </div>
      </div>
      
      {/* Pace Scenario Alert */}
      <div className={`rounded-lg border-2 p-4 mb-6 ${currentPace.color}`}>
        <h2 className="text-xl font-bold mb-2">{currentPace.title}</h2>
        <p className="text-sm">{currentPace.description}</p>
      </div>
      
      {/* Pace Profile Line Chart */}
      <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
        <h2 className="text-2xl font-bold mb-4 text-gray-800">
          Projected Race Flow
        </h2>
        <p className="text-sm text-gray-600 mb-4">
          Shows expected positions throughout the race. Lower = leading.
        </p>
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={lineChartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="call" />
            <YAxis reversed label={{ value: 'Position', angle: -90, position: 'insideLeft' }} />
            <Tooltip />
            <Legend />
            {race.horses.map((horse, idx) => (
              <Line
                key={horse.name}
                type="monotone"
                dataKey={horse.name}
                stroke={horse.color}
                strokeWidth={3}
                dot={{ r: 6 }}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      
      {/* Pace Fit Rankings */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-bold mb-4 text-gray-800">
            Pace Fit Rankings
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Higher score = better fit for projected pace scenario
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={paceFitData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" domain={[0, 100]} />
              <YAxis type="category" dataKey="name" width={120} />
              <Tooltip />
              <Bar dataKey="score" fill="#8884d8">
                {paceFitData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        {/* Speed vs Pace Scatter */}
        <div className="bg-white rounded-lg shadow-lg p-6">
          <h2 className="text-2xl font-bold mb-4 text-gray-800">
            Speed vs Pace Advantage
          </h2>
          <p className="text-sm text-gray-600 mb-4">
            Shows horses with both speed AND pace fit (top right = best)
          </p>
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                type="number" 
                dataKey="x" 
                name="Beyer" 
                label={{ value: 'Beyer Speed', position: 'bottom' }}
                domain={[70, 95]}
              />
              <YAxis 
                type="number" 
                dataKey="y" 
                name="Pace Score"
                label={{ value: 'Pace Fit', angle: -90, position: 'insideLeft' }}
                domain={[40, 90]}
              />
              <Tooltip 
                cursor={{ strokeDasharray: '3 3' }}
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="bg-white border-2 border-gray-300 rounded p-2 shadow-lg">
                        <p className="font-bold">{data.name}</p>
                        <p className="text-sm">Beyer: {data.x}</p>
                        <p className="text-sm">Pace: {data.y}</p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Scatter data={scatterData}>
                {scatterData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      </div>
      
      {/* Horse Details Table */}
      <div className="bg-white rounded-lg shadow-lg p-6">
        <h2 className="text-2xl font-bold mb-4 text-gray-800">
          Detailed Pace Analysis
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b-2 border-gray-300">
                <th className="text-left p-3">Horse</th>
                <th className="text-center p-3">Post</th>
                <th className="text-center p-3">Style</th>
                <th className="text-center p-3">Beyer</th>
                <th className="text-center p-3">Pace Fit</th>
                <th className="text-left p-3">Analysis</th>
              </tr>
            </thead>
            <tbody>
              {[...race.horses].sort((a, b) => b.paceScore - a.paceScore).map((horse, idx) => (
                <tr key={horse.name} className={`border-b border-gray-200 ${idx < 3 ? 'bg-green-50' : ''}`}>
                  <td className="p-3 font-semibold">{horse.name}</td>
                  <td className="text-center p-3">{horse.post}</td>
                  <td className="text-center p-3">
                    <span className="px-2 py-1 rounded text-xs font-bold" style={{ backgroundColor: horse.color, color: 'white' }}>
                      {horse.style}
                    </span>
                  </td>
                  <td className="text-center p-3">{horse.beyer}</td>
                  <td className="text-center p-3">
                    <span className="font-bold text-lg">{horse.paceScore}</span>
                  </td>
                  <td className="text-left p-3 text-sm">
                    {horse.paceScore >= 80 ? '✓ Excellent pace setup' :
                     horse.paceScore >= 65 ? '→ Good position' :
                     horse.paceScore >= 50 ? '⚠ Neutral setup' :
                     '✗ Difficult pace scenario'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      
      {/* Legend */}
      <div className="bg-white rounded-lg shadow-lg p-6 mt-6">
        <h3 className="text-xl font-bold mb-3 text-gray-800">Running Style Legend</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#ef4444' }}></div>
            <span className="text-sm"><strong>E</strong> - Early Speed (leads from gate)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#f97316' }}></div>
            <span className="text-sm"><strong>EP</strong> - Early Presser (near lead)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#eab308' }}></div>
            <span className="text-sm"><strong>P</strong> - Presser (mid-pack stalker)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 rounded" style={{ backgroundColor: '#22c55e' }}></div>
            <span className="text-sm"><strong>S</strong> - Sustained (closer)</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PaceVisualizationDashboard;