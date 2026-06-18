import { Canvas } from '@react-three/fiber'
import { OrbitControls, PerspectiveCamera, Environment, Float, Text, Line, Sphere } from '@react-three/drei'
import { useState, useEffect, useRef } from 'react'
import * as THREE from 'three'

interface ThoughtNode {
  id: string
  content: string
  position: [number, number, number]
  confidence: number
  layer: number
  timestamp: number
}

interface TokenProbability {
  token: string
  probability: number
  position: [number, number, number]
}

interface NeuralMapData {
  thoughts: ThoughtNode[]
  tokenProbabilities: TokenProbability[]
  connections: { from: string; to: string; strength: number }[]
}

function ThoughtNode({ node, onSelect, isSelected }: { 
  node: ThoughtNode; 
  onSelect: (node: ThoughtNode) => void;
  isSelected: boolean
}) {
  const [hovered, setHovered] = useState(false)
  const meshRef = useRef<THREE.Mesh>(null)

  const color = node.layer === 0 ? '#58a6ff' : 
                node.layer === 1 ? '#3fb950' : 
                node.layer === 2 ? '#f85149' : '#d29922'

  return (
    <Float speed={2} rotationIntensity={0.3} floatIntensity={0.3}>
      <mesh
        ref={meshRef}
        position={node.position}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
        onClick={() => onSelect(node)}
        scale={hovered || isSelected ? 1.3 : 1}
      >
        <sphereGeometry args={[0.3 + node.confidence * 0.2, 32, 32]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={hovered || isSelected ? 0.8 : 0.3}
          metalness={0.9}
          roughness={0.1}
          transparent
          opacity={0.9}
        />
      </mesh>
      {hovered || isSelected ? (
        <Text
          position={[node.position[0], node.position[1] + 0.6, node.position[2]]}
          fontSize={0.12}
          color="#ffffff"
          anchorX="center"
          anchorY="middle"
          maxWidth={2}
        >
          {node.content.substring(0, 30)}{node.content.length > 30 ? '...' : ''}
        </Text>
      ) : null}
      <Text
        position={[node.position[0], node.position[1] + 0.4, node.position[2]]}
        fontSize={0.08}
        color="#888888"
        anchorX="center"
        anchorY="middle"
      >
        {(node.confidence * 100).toFixed(0)}%
      </Text>
    </Float>
  )
}

function TokenVisualization({ tokens }: { tokens: TokenProbability[] }) {
  return (
    <group>
      {tokens.map((token, i) => (
        <group key={i} position={token.position}>
          <Sphere args={[0.1 + token.probability * 0.1, 16, 16]}>
            <meshStandardMaterial
              color="#a371f7"
              emissive="#a371f7"
              emissiveIntensity={token.probability}
              transparent
              opacity={0.7}
            />
          </Sphere>
          <Text
            position={[0, 0.2, 0]}
            fontSize={0.08}
            color="#ffffff"
            anchorX="center"
            anchorY="middle"
          >
            {token.token}
          </Text>
        </group>
      ))}
    </group>
  )
}

function Connection({ start, end, strength }: { 
  start: [number, number, number]; 
  end: [number, number, number]; 
  strength: number 
}) {
  const points = [new THREE.Vector3(...start), new THREE.Vector3(...end)]
  return (
    <Line
      points={points}
      color="#58a6ff"
      opacity={strength * 0.5}
      transparent
      lineWidth={strength * 2}
    />
  )
}

function KnowledgeGraph({ data, onNodeSelect, selectedNode }: {
  data: NeuralMapData
  onNodeSelect: (node: ThoughtNode) => void
  selectedNode: ThoughtNode | null
}) {
  const nodePositions = useRef<Map<string, [number, number, number]>>(new Map())
  
  useEffect(() => {
    data.thoughts.forEach(thought => {
      nodePositions.current.set(thought.id, thought.position)
    })
  }, [data.thoughts])

  return (
    <group>
      {/* Render connections first (behind nodes) */}
      {data.connections.map((conn, i) => {
        const startPos = nodePositions.current.get(conn.from)
        const endPos = nodePositions.current.get(conn.to)
        if (!startPos || !endPos) return null
        return (
          <Connection
            key={i}
            start={startPos}
            end={endPos}
            strength={conn.strength}
          />
        )
      })}

      {/* Render thought nodes */}
      {data.thoughts.map((node) => (
        <ThoughtNode
          key={node.id}
          node={node}
          onSelect={onNodeSelect}
          isSelected={selectedNode?.id === node.id}
        />
      ))}

      {/* Render token probabilities */}
      <TokenVisualization tokens={data.tokenProbabilities} />
    </group>
  )
}

export default function NeuralMap3D() {
  const [selectedNode, setSelectedNode] = useState<ThoughtNode | null>(null)
  const [data, setData] = useState<NeuralMapData>({
    thoughts: [],
    tokenProbabilities: [],
    connections: []
  })

  // Simulate real-time data updates
  useEffect(() => {
    const generateMockData = () => {
      const thoughts: ThoughtNode[] = [
        {
          id: '1',
          content: 'Understanding the problem context and requirements',
          position: [-2, 1, 0] as [number, number, number],
          confidence: 0.95,
          layer: 0,
          timestamp: Date.now()
        },
        {
          id: '2',
          content: 'Analyzing potential approaches and algorithms',
          position: [0, 2, 0] as [number, number, number],
          confidence: 0.88,
          layer: 1,
          timestamp: Date.now()
        },
        {
          id: '3',
          content: 'Implementing the solution with optimal complexity',
          position: [2, 1, 0] as [number, number, number],
          confidence: 0.92,
          layer: 2,
          timestamp: Date.now()
        },
        {
          id: '4',
          content: 'Refining the implementation for edge cases',
          position: [0, 0, 1] as [number, number, number],
          confidence: 0.85,
          layer: 1,
          timestamp: Date.now()
        },
        {
          id: '5',
          content: 'Validating results against test cases',
          position: [-1, -1, 0] as [number, number, number],
          confidence: 0.90,
          layer: 2,
          timestamp: Date.now()
        }
      ]

      const tokenProbabilities: TokenProbability[] = [
        { token: 'function', probability: 0.95, position: [-2.5, 0.5, 0.5] as [number, number, number] },
        { token: 'import', probability: 0.88, position: [-1.5, 0.3, 0.3] as [number, number, number] },
        { token: 'class', probability: 0.72, position: [0.5, 1.5, 0.5] as [number, number, number] },
        { token: 'return', probability: 0.91, position: [2.5, 0.5, 0.3] as [number, number, number] },
        { token: 'if', probability: 0.83, position: [0.3, -0.5, 0.8] as [number, number, number] },
      ]

      const connections = [
        { from: '1', to: '2', strength: 0.9 },
        { from: '2', to: '3', strength: 0.85 },
        { from: '2', to: '4', strength: 0.7 },
        { from: '3', to: '5', strength: 0.8 },
        { from: '4', to: '5', strength: 0.75 },
      ]

      setData({ thoughts, tokenProbabilities, connections })
    }

    generateMockData()
    const interval = setInterval(generateMockData, 3000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <h2 className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-arena-muted">
          <span className="w-2 h-2 rounded-full bg-arena-blue animate-pulse"></span>
          3D Neural Map
        </h2>
        <div className="flex items-center gap-4 text-xs text-arena-muted">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#58a6ff]"></span>
            <span>Input Layer</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#3fb950]"></span>
            <span>Hidden Layer</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#f85149]"></span>
            <span>Output Layer</span>
          </div>
        </div>
      </div>
      
      <div className="relative h-[500px] rounded-lg overflow-hidden bg-[rgba(1,4,9,0.5)] border border-arena-border">
        <Canvas>
          <PerspectiveCamera makeDefault position={[0, 0, 10]} />
          <OrbitControls 
            enableZoom={true} 
            enablePan={true} 
            enableRotate={true}
            maxDistance={20}
            minDistance={5}
          />
          <Environment preset="night" />
          
          <ambientLight intensity={0.4} />
          <pointLight position={[10, 10, 10]} intensity={1.2} />
          <pointLight position={[-10, -10, -10]} intensity={0.6} color="#58a6ff" />
          <pointLight position={[0, 10, 0]} intensity={0.4} color="#3fb950" />

          <KnowledgeGraph 
            data={data} 
            onNodeSelect={setSelectedNode}
            selectedNode={selectedNode}
          />
        </Canvas>

        {/* Selected Node Info Panel */}
        {selectedNode && (
          <div className="absolute bottom-4 left-4 right-4 p-4 rounded-lg bg-[rgba(1,4,9,0.9)] border border-arena-border backdrop-blur-sm">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h3 className="text-sm font-semibold text-arena-blue mb-2">
                  Thought Node #{selectedNode.id}
                </h3>
                <p className="text-sm text-gray-300 mb-2">{selectedNode.content}</p>
                <div className="flex items-center gap-4 text-xs text-arena-muted">
                  <span>Confidence: {(selectedNode.confidence * 100).toFixed(1)}%</span>
                  <span>Layer: {selectedNode.layer}</span>
                  <span className="text-arena-blue">
                    {new Date(selectedNode.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                className="p-2 rounded hover:bg-white/10 transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}