import { Canvas } from '@react-three/fiber'
import { OrbitControls, PerspectiveCamera, Environment, Float, Text, Line, Sphere, Trail } from '@react-three/drei'
import { useState, useEffect, useRef } from 'react'
import * as THREE from 'three'
import { Activity, Cpu, MemoryStick, Zap } from 'lucide-react'

interface BattleAgent {
  id: string
  name: string
  position: [number, number, number]
  color: string
  score: number
  health: number
  energy: number
  model: string
}

interface BattleAction {
  agentId: string
  type: 'attack' | 'defend' | 'collaborate' | 'analyze'
  position: [number, number, number]
  target?: string
  timestamp: number
}

interface MultiAgentCollaboration {
  agents: string[]
  task: string
  progress: number
  position: [number, number, number]
}

interface HardwareTelemetry {
  cpu: number
  memory: number
  gpu: number
  power: number
}

interface BattleData {
  agents: BattleAgent[]
  actions: BattleAction[]
  collaborations: MultiAgentCollaboration[]
  telemetry: HardwareTelemetry
}

function BattleAgentModel({ agent, isAttacking }: { 
  agent: BattleAgent
  isAttacking: boolean 
}) {
  const [hovered, setHovered] = useState(false)
  const meshRef = useRef<THREE.Mesh>(null)

  return (
    <Float speed={1.5} rotationIntensity={0.5} floatIntensity={0.3}>
      <group position={agent.position}>
        {/* Agent core */}
        <mesh
          ref={meshRef}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
          scale={hovered ? 1.2 : 1}
        >
          <octahedronGeometry args={[0.6, 0]} />
          <meshStandardMaterial
            color={agent.color}
            emissive={agent.color}
            emissiveIntensity={isAttacking ? 1.0 : 0.4}
            metalness={0.9}
            roughness={0.1}
          />
        </mesh>

        {/* Health ring */}
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.8, 0.05, 16, 100]} />
          <meshStandardMaterial
            color={agent.health > 50 ? '#3fb950' : agent.health > 25 ? '#d29922' : '#f85149'}
            emissive={agent.health > 50 ? '#3fb950' : agent.health > 25 ? '#d29922' : '#f85149'}
            emissiveIntensity={0.5}
          />
        </mesh>

        {/* Energy indicators */}
        {Array.from({ length: 4 }).map((_, i) => (
          <mesh key={i} position={[0, 0.9 + i * 0.15, 0]}>
            <sphereGeometry args={[0.05, 8, 8]} />
            <meshStandardMaterial
              color={i < agent.energy / 25 ? '#a371f7' : '#333'}
              emissive={i < agent.energy / 25 ? '#a371f7' : '#333'}
              emissiveIntensity={0.8}
            />
          </mesh>
        ))}

        {/* Agent name */}
        <Text
          position={[0, 1.5, 0]}
          fontSize={0.15}
          color="#ffffff"
          anchorX="center"
          anchorY="middle"
        >
          {agent.name}
        </Text>

        {/* Score display */}
        <Text
          position={[0, -1.2, 0]}
          fontSize={0.12}
          color={agent.color}
          anchorX="center"
          anchorY="middle"
        >
          {agent.score.toFixed(0)}
        </Text>
      </group>
    </Float>
  )
}

function ActionEffect({ action }: { action: BattleAction }) {
  const color = action.type === 'attack' ? '#f85149' : 
                action.type === 'defend' ? '#58a6ff' : 
                action.type === 'collaborate' ? '#3fb950' : '#d29922'

  return (
    <Float speed={3} rotationIntensity={1} floatIntensity={0.5}>
      <mesh position={action.position}>
        <sphereGeometry args={[0.3, 16, 16]} />
        <meshStandardMaterial
          color={color}
          emissive={color}
          emissiveIntensity={1}
          transparent
          opacity={0.8}
        />
      </mesh>
    </Float>
  )
}

function CollaborationZone({ collaboration }: { collaboration: MultiAgentCollaboration }) {
  return (
    <group position={collaboration.position}>
      {/* Collaboration sphere */}
      <mesh>
        <sphereGeometry args={[1.5, 32, 32]} />
        <meshStandardMaterial
          color="#3fb950"
          emissive="#3fb950"
          emissiveIntensity={0.2}
          transparent
          opacity={0.1}
          wireframe
        />
      </mesh>

      {/* Progress indicator */}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[1.5, 0.1, 16, 100, 0, (collaboration.progress / 100) * Math.PI * 2]} />
        <meshStandardMaterial
          color="#3fb950"
          emissive="#3fb950"
          emissiveIntensity={0.8}
        />
      </mesh>

      <Text
        position={[0, 2, 0]}
        fontSize={0.12}
        color="#3fb950"
        anchorX="center"
        anchorY="middle"
      >
        {collaboration.task}
      </Text>
    </group>
  )
}

function TelemetryOverlay({ telemetry }: { telemetry: HardwareTelemetry }) {
  return (
    <div className="absolute top-4 right-4 p-4 rounded-lg bg-[rgba(1,4,9,0.9)] border border-arena-border backdrop-blur-sm space-y-3">
      <h3 className="text-xs font-extrabold uppercase tracking-wider text-arena-muted mb-3">
        Hardware Telemetry
      </h3>
      
      <div className="flex items-center gap-3">
        <Cpu className="w-4 h-4 text-arena-blue" />
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-400">CPU</span>
            <span className="text-arena-blue">{telemetry.cpu}%</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-arena-blue transition-all duration-300"
              style={{ width: `${telemetry.cpu}%` }}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <MemoryStick className="w-4 h-4 text-arena-green" />
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-400">Memory</span>
            <span className="text-arena-green">{telemetry.memory}%</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-arena-green transition-all duration-300"
              style={{ width: `${telemetry.memory}%` }}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Activity className="w-4 h-4 text-purple-500" />
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-400">GPU</span>
            <span className="text-purple-500">{telemetry.gpu}%</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-purple-500 transition-all duration-300"
              style={{ width: `${telemetry.gpu}%` }}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Zap className="w-4 h-4 text-yellow-500" />
        <div className="flex-1">
          <div className="flex justify-between text-xs mb-1">
            <span className="text-gray-400">Power</span>
            <span className="text-yellow-500">{telemetry.power}W</span>
          </div>
          <div className="h-1 bg-gray-700 rounded-full overflow-hidden">
            <div 
              className="h-full bg-yellow-500 transition-all duration-300"
              style={{ width: `${Math.min(telemetry.power / 5, 100)}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function BattleVisualizer() {
  const [battleData, setBattleData] = useState<BattleData>({
    agents: [],
    actions: [],
    collaborations: [],
    telemetry: { cpu: 0, memory: 0, gpu: 0, power: 0 }
  })
  const [attackingAgent, setAttackingAgent] = useState<string | null>(null)

  // Simulate real-time battle data
  useEffect(() => {
    const generateMockBattleData = () => {
      const agents: BattleAgent[] = [
        {
          id: '1',
          name: 'llama3.2:3b',
          position: [-3, 0, 0] as [number, number, number],
          color: '#58a6ff',
          score: 1250,
          health: 85,
          energy: 75,
          model: 'llama3.2:3b'
        },
        {
          id: '2',
          name: 'qwen2.5:7b',
          position: [3, 0, 0] as [number, number, number],
          color: '#3fb950',
          score: 1320,
          health: 92,
          energy: 90,
          model: 'qwen2.5:7b'
        },
        {
          id: '3',
          name: 'mistral:7b',
          position: [0, 2, 0] as [number, number, number],
          color: '#f85149',
          score: 1280,
          health: 78,
          energy: 65,
          model: 'mistral:7b'
        }
      ]

      const actions: BattleAction[] = [
        {
          agentId: '1',
          type: 'attack',
          position: [-1.5, 0, 0] as [number, number, number],
          target: '2',
          timestamp: Date.now()
        },
        {
          agentId: '2',
          type: 'defend',
          position: [1.5, 0, 0] as [number, number, number],
          timestamp: Date.now()
        }
      ]

      const collaborations: MultiAgentCollaboration[] = [
        {
          agents: ['1', '3'],
          task: 'Code Refactoring',
          progress: 67,
          position: [0, 0, 2] as [number, number, number]
        }
      ]

      const telemetry: HardwareTelemetry = {
        cpu: Math.random() * 30 + 40,
        memory: Math.random() * 20 + 60,
        gpu: Math.random() * 40 + 50,
        power: Math.random() * 100 + 150
      }

      setBattleData({ agents, actions, collaborations, telemetry })

      // Random attacking agent
      const randomAgent = agents[Math.floor(Math.random() * agents.length)].id
      setAttackingAgent(randomAgent)
    }

    generateMockBattleData()
    const interval = setInterval(generateMockBattleData, 2000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-6">
        <h2 className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wider text-arena-muted">
          <span className="w-2 h-2 rounded-full bg-arena-red animate-pulse"></span>
          3D Battle Visualization
        </h2>
        <div className="flex items-center gap-4 text-xs text-arena-muted">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#f85149]"></span>
            <span>Attack</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#58a6ff]"></span>
            <span>Defend</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#3fb950]"></span>
            <span>Collaborate</span>
          </div>
        </div>
      </div>

      <div className="relative h-[500px] rounded-lg overflow-hidden bg-[rgba(1,4,9,0.5)] border border-arena-border">
        <Canvas>
          <PerspectiveCamera makeDefault position={[0, 5, 12]} />
          <OrbitControls 
            enableZoom={true} 
            enablePan={true} 
            enableRotate={true}
            maxDistance={25}
            minDistance={8}
          />
          <Environment preset="night" />
          
          <ambientLight intensity={0.3} />
          <pointLight position={[10, 10, 10]} intensity={1.5} />
          <pointLight position={[-10, -10, -10]} intensity={0.8} color="#f85149" />
          <pointLight position={[0, -10, 5]} intensity={0.5} color="#3fb950" />

          {/* Battle arena floor */}
          <mesh rotation={[Math.PI / 2, 0, 0]} position={[0, -3, 0]}>
            <circleGeometry args={[8, 64]} />
            <meshStandardMaterial
              color="#1a1a2e"
              emissive="#1a1a2e"
              emissiveIntensity={0.2}
              transparent
              opacity={0.5}
            />
          </mesh>

          {/* Grid lines on arena floor */}
          {Array.from({ length: 10 }).map((_, i) => (
            <Line
              key={`h-${i}`}
              points={[
                new THREE.Vector3(-7, -2.9, -7 + i * 1.5),
                new THREE.Vector3(7, -2.9, -7 + i * 1.5)
              ]}
              color="#58a6ff"
              opacity={0.2}
              transparent
              lineWidth={1}
            />
          ))}
          {Array.from({ length: 10 }).map((_, i) => (
            <Line
              key={`v-${i}`}
              points={[
                new THREE.Vector3(-7 + i * 1.5, -2.9, -7),
                new THREE.Vector3(-7 + i * 1.5, -2.9, 7)
              ]}
              color="#58a6ff"
              opacity={0.2}
              transparent
              lineWidth={1}
            />
          ))}

          {/* Render battle agents */}
          {battleData.agents.map((agent) => (
            <BattleAgentModel
              key={agent.id}
              agent={agent}
              isAttacking={attackingAgent === agent.id}
            />
          ))}

          {/* Render actions */}
          {battleData.actions.map((action, i) => (
            <ActionEffect key={i} action={action} />
          ))}

          {/* Render collaboration zones */}
          {battleData.collaborations.map((collab, i) => (
            <CollaborationZone key={i} collaboration={collab} />
          ))}
        </Canvas>

        {/* Telemetry overlay */}
        <TelemetryOverlay telemetry={battleData.telemetry} />

        {/* Battle stats overlay */}
        <div className="absolute bottom-4 left-4 p-4 rounded-lg bg-[rgba(1,4,9,0.9)] border border-arena-border backdrop-blur-sm">
          <h3 className="text-xs font-extrabold uppercase tracking-wider text-arena-muted mb-3">
            Live Battle Stats
          </h3>
          <div className="space-y-2">
            {battleData.agents.map((agent) => (
              <div key={agent.id} className="flex items-center justify-between text-sm">
                <span className="text-gray-300">{agent.name}</span>
                <div className="flex items-center gap-4">
                  <span className="text-xs text-arena-muted">HP: {agent.health}%</span>
                  <span className="font-bold" style={{ color: agent.color }}>
                    {agent.score.toFixed(0)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}