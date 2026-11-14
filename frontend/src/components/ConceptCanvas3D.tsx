import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

export interface Concept3DProps {
  conceptType?: 'transformer_architecture' | 'neural_network' | 'distributed_cluster' | 'molecule' | 'quantum_bloch' | 'generic';
  title?: string;
  description?: string;
}

interface LayerMetadata {
  id: string;
  title: string;
  shortName: string;
  color: string;
  hexColor: number;
  math: string;
  role: string;
  details: string;
  tensorShape?: string;
  params?: string;
  flops?: string;
}

// ── 1. TRANSFORMER SPECIFIC ARCHITECTURAL STAGES ────────────────────────────
const TRANSFORMER_STAGES: LayerMetadata[] = [
  {
    id: 'stage-embeddings',
    title: 'Input Token Embeddings & Positional Encoding',
    shortName: 'Token Embedding [E+P]',
    color: '#10B981',
    hexColor: 0x10b981,
    math: 'x_i = W_e(t_i) + PE(pos, 2i)',
    role: 'Vector Tokenization',
    details: 'Converts input words/tokens into dense 768-dim continuous vectors, adding sinusoidal wave positional frequencies so the model retains token order without recurrence.',
    tensorShape: '[B, 512, 768]',
    params: '23.44M Params (Vocab 30,522 x 768)',
    flops: '0.05 GFLOPs',
  },
  {
    id: 'stage-attention',
    title: 'Multi-Head Self-Attention Module (8 Parallel Heads)',
    shortName: 'Multi-Head Attention (Q,K,V)',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: 'MultiHead(Q,K,V) = Concat(head_1..head_8) W^O',
    role: 'Parallel Context Heads',
    details: 'Splits representations into 8 parallel attention heads across Query (Q), Key (K), and Value (V) projections. Calculates pairwise token affinity dot-products simultaneously in O(1) sequential operations.',
    tensorShape: '[B, 8, 512, 64]',
    params: '2.36M Params (4 x 768 x 768)',
    flops: '7.08 GFLOPs',
  },
  {
    id: 'stage-residual-1',
    title: 'Curved Residual Skip-Connection 1 (Add & Norm)',
    shortName: 'Residual Highway 1',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'x\' = LayerNorm(x + Sublayer(x))',
    role: 'Gradient Bypass Highway',
    details: 'The curved glowing bypass pipe looping OVER the attention block delivers input x directly to the LayerNorm slab, preventing vanishing gradients in deep Transformer stacks.',
    tensorShape: '[B, 512, 768]',
    params: '1.54K Params (γ, β scale/bias)',
    flops: '0.02 GFLOPs',
  },
  {
    id: 'stage-ffn',
    title: 'Position-Wise Feed-Forward Network (FFN)',
    shortName: 'Feed-Forward [FFN]',
    color: '#EC4899',
    hexColor: 0xec4899,
    math: 'FFN(x\') = max(0, x\' W_1 + b_1) W_2 + b_2',
    role: 'Non-Linear Abstraction',
    details: 'Dense two-layer expansion (typically 4x d_model = 3072-dim) with GELU activation applied identically to each token position individually, followed by a secondary residual skip connection.',
    tensorShape: '[B, 512, 3072]',
    params: '4.72M Params (2 x 768 x 3072)',
    flops: '9.44 GFLOPs',
  },
  {
    id: 'stage-output',
    title: 'Linear Unembedding & Softmax Probability Logits',
    shortName: 'Softmax Vocabulary Logits',
    color: '#F59E0B',
    hexColor: 0xf59e0b,
    math: 'P(w_t | w_<t) = softmax(W_vocab h_t)',
    role: 'Vocabulary Probability',
    details: 'Projects the final hidden states into vocabulary dimensions, passing through a temperature-controlled softmax to yield token probability distributions.',
    tensorShape: '[B, 512, 30522]',
    params: '23.44M Params (Tied weights)',
    flops: '5.01 GFLOPs',
  },
];

// ── 2. STANDARD MULTI-LAYER PERCEPTRON (MLP) LAYERS ─────────────────────────
const MLP_LAYERS: LayerMetadata[] = [
  {
    id: 'mlp-input',
    title: 'Input Features Layer (X)',
    shortName: 'Input Features (X)',
    color: '#10B981',
    hexColor: 0x10b981,
    math: 'a^[0] = x',
    role: 'Input Scalar Vector',
    details: 'Raw normalized input feature vectors passed to the first layer of the multi-layer perceptron.',
    tensorShape: '[B, 784]',
    params: '0 Params',
    flops: '0.00 GFLOPs',
  },
  {
    id: 'mlp-hidden-1',
    title: 'Hidden Layer 1 (Dense ReLU)',
    shortName: 'Hidden Layer 1',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: 'z^[1] = W^[1] x + b^[1], a^[1] = ReLU(z^[1])',
    role: 'Feature Extraction',
    details: 'Dense fully connected layer applying affine transformation followed by rectified linear unit activation.',
    tensorShape: '[B, 256]',
    params: '200.9K Params (784 x 256)',
    flops: '0.40 GFLOPs',
  },
  {
    id: 'mlp-hidden-2',
    title: 'Hidden Layer 2 (Dense ReLU)',
    shortName: 'Hidden Layer 2',
    color: '#EC4899',
    hexColor: 0xec4899,
    math: 'z^[2] = W^[2] a^[1] + b^[2], a^[2] = ReLU(z^[2])',
    role: 'Deep Representations',
    details: 'Second dense layer forming hierarchical high-dimensional feature combinations.',
    tensorShape: '[B, 128]',
    params: '32.8K Params (256 x 128)',
    flops: '0.07 GFLOPs',
  },
  {
    id: 'mlp-output',
    title: 'Output Layer (Prediction Logits)',
    shortName: 'Output Logits (Y)',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'y_hat = softmax(W^[3] a^[2] + b^[3])',
    role: 'Prediction Head',
    details: 'Final linear transformation producing classification or regression target outputs.',
    tensorShape: '[B, 10]',
    params: '1.29K Params (128 x 10)',
    flops: '0.003 GFLOPs',
  },
];

// ── 3. RESNET-50 CONVOLUTIONAL ARCHITECTURE ─────────────────────────────────
const RESNET_STAGES: LayerMetadata[] = [
  {
    id: 'resnet-conv1',
    title: 'Initial Convolution (Conv2d 7x7, Stride 2)',
    shortName: 'Conv1 (7x7, s=2)',
    color: '#10B981',
    hexColor: 0x10b981,
    math: 'y = Conv2d(x, W_{7x7}, stride=2, pad=3)',
    role: 'Spatial Downsampling',
    details: 'Initial receptive field expansion downsampling 224x224 RGB inputs into 64 feature channels (112x112 spatial resolution).',
    tensorShape: '[B, 64, 112, 112]',
    params: '9.4K Params (7x7x3x64)',
    flops: '0.24 GFLOPs',
  },
  {
    id: 'resnet-bn1',
    title: 'BatchNorm2d & MaxPool (3x3, s=2)',
    shortName: 'BatchNorm & MaxPool',
    color: '#38BDF8',
    hexColor: 0x38bdf8,
    math: 'x\' = MaxPool(ReLU(BatchNorm(y)))',
    role: 'Distribution Normalization',
    details: 'Zero-mean unit-variance stabilization across mini-batches, followed by 3x3 max pooling with stride 2 reducing spatial map to 56x56.',
    tensorShape: '[B, 64, 56, 56]',
    params: '128 Params',
    flops: '0.02 GFLOPs',
  },
  {
    id: 'resnet-bottleneck',
    title: 'Residual Bottleneck Block (1x1 -> 3x3 -> 1x1)',
    shortName: 'Residual Bottleneck',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: 'F(x) = W_3 * ReLU(W_2 * ReLU(W_1 * x)), Out = ReLU(x + F(x))',
    role: 'Identity Skip Highway',
    details: 'Dimensionality reduction with 1x1 conv, spatial 3x3 conv, and 1x1 restoration. The identity shortcut x + F(x) allows gradients to flow directly without vanishing.',
    tensorShape: '[B, 256, 56, 56]',
    params: '70.4K Params (Bottleneck Unit)',
    flops: '1.45 GFLOPs',
  },
  {
    id: 'resnet-avgpool',
    title: 'Global Average Pooling (7x7 -> 1x1)',
    shortName: 'Global AvgPool',
    color: '#EC4899',
    hexColor: 0xec4899,
    math: 'GAP(x) = (1 / HW) * sum_{h,w} x_{c,h,w}',
    role: 'Spatial Collapse',
    details: 'Reduces spatial dimensions from 7x7 to 1x1 per channel, drastically lowering parameter count compared to fully connected flattening.',
    tensorShape: '[B, 2048, 1, 1]',
    params: '0 Params',
    flops: '0.01 GFLOPs',
  },
  {
    id: 'resnet-fc',
    title: 'Final Classification Head (Dense Linear 1000)',
    shortName: 'Linear Head (1000)',
    color: '#F59E0B',
    hexColor: 0xf59e0b,
    math: 'y_logits = W_{fc} * GAP(x) + b_{fc}',
    role: 'Class Logits',
    details: 'Linear projection producing 1000 ImageNet category logits, converted to normalized probabilities via Softmax.',
    tensorShape: '[B, 1000]',
    params: '2.05M Params (2048 x 1000)',
    flops: '0.004 GFLOPs',
  },
];

// Helper: 3D Billboard Text Label Sprite
function createTextSprite(primary: string, secondary: string, color: string): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 140;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.clearRect(0, 0, 512, 140);
    ctx.fillStyle = 'rgba(6, 10, 23, 0.9)';
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(10, 10, 492, 120, 24);
    ctx.fill();
    ctx.stroke();

    ctx.font = 'bold 34px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.fillText(primary, 256, 62);

    ctx.font = '500 22px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillStyle = '#94A3B8';
    ctx.fillText(secondary, 256, 102);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.minFilter = THREE.LinearFilter;
  const mat = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(3.4, 0.95, 1);
  return sprite;
}

// ── COMPUTE DAG (NETRON / ONNX GRAPH) COMPONENT ─────────────────────────────
interface ComputeDAGProps {
  modelType: 'transformer_architecture' | 'neural_network' | 'resnet50';
  selectedLayerId: string | null;
  onSelectLayer: (layer: LayerMetadata) => void;
}

const ComputeDAGView: React.FC<ComputeDAGProps> = ({ modelType, selectedLayerId, onSelectLayer }) => {
  const stages = modelType === 'transformer_architecture'
    ? TRANSFORMER_STAGES
    : modelType === 'resnet50'
    ? RESNET_STAGES
    : MLP_LAYERS;

  return (
    <div style={{ flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#050914', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Telemetry Header */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.75rem' }}>
        <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '8px', padding: '0.75rem' }}>
          <div style={{ fontSize: '0.65rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Framework Runtime</div>
          <div style={{ fontSize: '0.9rem', color: '#38BDF8', fontWeight: 700 }}>PyTorch 2.4 · ONNX v1.16</div>
        </div>
        <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '8px', padding: '0.75rem' }}>
          <div style={{ fontSize: '0.65rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Parameter Count</div>
          <div style={{ fontSize: '0.9rem', color: '#A78BFA', fontWeight: 700 }}>
            {modelType === 'transformer_architecture' ? '110.1M (Bert/GPT Small)' : modelType === 'resnet50' ? '25.6M (ResNet-50)' : '235.0K (3-Layer MLP)'}
          </div>
        </div>
        <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '8px', padding: '0.75rem' }}>
          <div style={{ fontSize: '0.65rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Compute FLOPs</div>
          <div style={{ fontSize: '0.9rem', color: '#10B981', fontWeight: 700 }}>
            {modelType === 'transformer_architecture' ? '21.60 GFLOPs' : modelType === 'resnet50' ? '4.10 GFLOPs' : '0.47 GFLOPs'}
          </div>
        </div>
        <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(245, 158, 11, 0.3)', borderRadius: '8px', padding: '0.75rem' }}>
          <div style={{ fontSize: '0.65rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase' }}>Precision & Memory</div>
          <div style={{ fontSize: '0.9rem', color: '#F59E0B', fontWeight: 700 }}>BF16 · 440 MB Tensor Footprint</div>
        </div>
      </div>

      {/* Interactive Computational DAG Pipeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', maxWidth: '820px', margin: '0 auto', width: '100%' }}>
        {stages.map((stage, idx) => {
          const isSelected = selectedLayerId === stage.id;
          return (
            <React.Fragment key={stage.id}>
              {/* Operator Node Block */}
              <div
                onClick={() => onSelectLayer(stage)}
                style={{
                  background: isSelected ? 'rgba(56, 189, 248, 0.14)' : 'rgba(15, 23, 42, 0.85)',
                  border: `1px solid ${isSelected ? stage.color : 'rgba(255, 255, 255, 0.1)'}`,
                  borderRadius: '10px',
                  padding: '1rem 1.25rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                  boxShadow: isSelected ? `0 0 20px ${stage.color}33` : '0 4px 12px rgba(0,0,0,0.3)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      background: `${stage.color}25`,
                      border: `1px solid ${stage.color}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 800,
                      color: stage.color,
                      fontSize: '0.85rem',
                    }}
                  >
                    {idx + 1}
                  </div>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.95rem', fontWeight: 700, color: '#F8FAFC' }}>{stage.title}</span>
                      <span style={{ fontSize: '0.65rem', padding: '2px 6px', borderRadius: '4px', background: `${stage.color}20`, color: stage.color, fontWeight: 700 }}>
                        {stage.role}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.72rem', color: '#94A3B8', marginTop: '3px', fontFamily: 'monospace' }}>
                      {stage.math}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
                  {stage.tensorShape && (
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '0.65rem', color: '#64748B' }}>TENSOR SHAPE</div>
                      <code style={{ fontSize: '0.75rem', color: '#38BDF8', fontWeight: 600 }}>{stage.tensorShape}</code>
                    </div>
                  )}
                  {stage.params && (
                    <div style={{ textAlign: 'right', display: 'none', minWidth: '110px' }} className="d-md-block">
                      <div style={{ fontSize: '0.65rem', color: '#64748B' }}>PARAMS / FLOPS</div>
                      <div style={{ fontSize: '0.72rem', color: '#F1F5F9' }}>{stage.params.split('(')[0]}</div>
                    </div>
                  )}
                  <span style={{ color: stage.color, fontSize: '1rem' }}>➔</span>
                </div>
              </div>

              {/* Dataflow Arrow with Residual indicator if applicable */}
              {idx < stages.length - 1 && (
                <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', position: 'relative', height: '24px' }}>
                  <div style={{ width: '2px', height: '100%', background: 'linear-gradient(to bottom, rgba(56,189,248,0.6), rgba(139,92,246,0.6))' }} />
                  {stage.id.includes('residual') && (
                    <span style={{ position: 'absolute', right: '15%', fontSize: '0.68rem', color: '#38BDF8', background: 'rgba(56,189,248,0.1)', padding: '2px 8px', borderRadius: '4px', border: '1px solid rgba(56,189,248,0.3)' }}>
                      ⚡ Gradient Skip Highway (x + F(x))
                    </span>
                  )}
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};

// ── SELF-ATTENTION MATRIX HEATMAP COMPONENT ─────────────────────────────────
const AttentionHeatmapView: React.FC = () => {
  const TOKENS = ['The', 'academic', 'librarian', 'attends', 'to', 'knowledge', 'queries', '[EOS]'];
  const [activeHead, setActiveHead] = useState<number>(0);
  const [hoveredCell, setHoveredCell] = useState<{ i: number; j: number } | null>(null);

  // Synthetic normalized attention matrices for 4 distinct heads
  const HEAD_MATRICES = [
    // Head 1: Syntactic Dependencies (Verb-Preposition & Adjective-Noun links)
    [
      [0.65, 0.15, 0.05, 0.05, 0.02, 0.03, 0.03, 0.02],
      [0.04, 0.12, 0.72, 0.02, 0.02, 0.03, 0.03, 0.02],
      [0.08, 0.35, 0.42, 0.05, 0.02, 0.03, 0.03, 0.02],
      [0.02, 0.02, 0.12, 0.10, 0.62, 0.04, 0.05, 0.03],
      [0.01, 0.01, 0.02, 0.04, 0.15, 0.68, 0.06, 0.03],
      [0.01, 0.02, 0.03, 0.02, 0.04, 0.22, 0.62, 0.04],
      [0.02, 0.03, 0.24, 0.05, 0.02, 0.48, 0.12, 0.04],
      [0.05, 0.05, 0.10, 0.05, 0.05, 0.10, 0.10, 0.50],
    ],
    // Head 2: Semantic Coreference (Queries <-> Librarian <-> Knowledge)
    [
      [0.70, 0.05, 0.08, 0.04, 0.03, 0.04, 0.04, 0.02],
      [0.05, 0.30, 0.52, 0.03, 0.02, 0.04, 0.02, 0.02],
      [0.02, 0.22, 0.45, 0.08, 0.03, 0.12, 0.06, 0.02],
      [0.03, 0.04, 0.38, 0.25, 0.05, 0.15, 0.08, 0.02],
      [0.02, 0.02, 0.08, 0.12, 0.45, 0.22, 0.06, 0.03],
      [0.02, 0.04, 0.28, 0.05, 0.04, 0.42, 0.12, 0.03],
      [0.02, 0.05, 0.42, 0.04, 0.03, 0.35, 0.07, 0.02],
      [0.04, 0.04, 0.18, 0.04, 0.04, 0.18, 0.18, 0.30],
    ],
    // Head 3: Positional Locality (Diagonal window attention)
    [
      [0.72, 0.22, 0.03, 0.01, 0.01, 0.00, 0.00, 0.01],
      [0.24, 0.58, 0.14, 0.02, 0.01, 0.00, 0.00, 0.01],
      [0.02, 0.26, 0.52, 0.16, 0.02, 0.01, 0.00, 0.01],
      [0.01, 0.02, 0.22, 0.50, 0.21, 0.02, 0.01, 0.01],
      [0.00, 0.01, 0.02, 0.24, 0.48, 0.21, 0.03, 0.01],
      [0.00, 0.00, 0.01, 0.02, 0.26, 0.52, 0.17, 0.02],
      [0.00, 0.00, 0.00, 0.01, 0.03, 0.28, 0.56, 0.12],
      [0.01, 0.01, 0.01, 0.01, 0.02, 0.05, 0.24, 0.65],
    ],
    // Head 4: Global Sequence Aggregator
    [
      [0.18, 0.12, 0.16, 0.11, 0.08, 0.14, 0.11, 0.10],
      [0.10, 0.20, 0.22, 0.12, 0.08, 0.12, 0.10, 0.06],
      [0.08, 0.15, 0.28, 0.14, 0.06, 0.15, 0.10, 0.04],
      [0.06, 0.08, 0.22, 0.24, 0.12, 0.16, 0.08, 0.04],
      [0.05, 0.06, 0.12, 0.14, 0.26, 0.22, 0.10, 0.05],
      [0.06, 0.08, 0.16, 0.12, 0.10, 0.28, 0.14, 0.06],
      [0.08, 0.10, 0.24, 0.10, 0.08, 0.22, 0.14, 0.04],
      [0.12, 0.12, 0.15, 0.10, 0.08, 0.15, 0.12, 0.16],
    ],
  ];

  const currentMatrix = HEAD_MATRICES[activeHead];
  const HEAD_NAMES = [
    'Head 1: Syntactic Dependencies',
    'Head 2: Semantic Coreference',
    'Head 3: Positional Locality',
    'Head 4: Global Sequence Context',
  ];

  return (
    <div style={{ flex: 1, padding: '1.5rem', overflowY: 'auto', background: '#050914', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Head Selector */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#F8FAFC', margin: 0 }}>
            Scaled Dot-Product Self-Attention Heatmap (Vaswani et al.)
          </h3>
          <div style={{ fontSize: '0.75rem', color: '#64748B' }}>
            Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V · d_k = 64
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.4rem', background: 'rgba(255,255,255,0.04)', padding: '3px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)' }}>
          {HEAD_NAMES.map((name, hIdx) => (
            <button
              key={hIdx}
              type="button"
              onClick={() => setActiveHead(hIdx)}
              style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                padding: '0.35rem 0.65rem',
                borderRadius: '6px',
                border: 'none',
                background: activeHead === hIdx ? '#8B5CF6' : 'transparent',
                color: activeHead === hIdx ? '#FFFFFF' : '#94A3B8',
                cursor: 'pointer',
              }}
            >
              {name.split(':')[0]}
            </button>
          ))}
        </div>
      </div>

      {/* Visual Token Connector Banner */}
      <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '8px', padding: '0.75rem 1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.8rem', color: '#A78BFA', fontWeight: 700 }}>Active Head:</span>
          <span style={{ fontSize: '0.8rem', color: '#F1F5F9' }}>{HEAD_NAMES[activeHead]}</span>
        </div>
        {hoveredCell ? (
          <div style={{ fontSize: '0.78rem', color: '#38BDF8', fontWeight: 600 }}>
            Query [{TOKENS[hoveredCell.i]}] ➔ Key [{TOKENS[hoveredCell.j]}] · Attention Weight: {(currentMatrix[hoveredCell.i][hoveredCell.j] * 100).toFixed(1)}%
          </div>
        ) : (
          <div style={{ fontSize: '0.75rem', color: '#64748B' }}>Hover over any matrix cell to inspect pairwise token affinity</div>
        )}
      </div>

      {/* Heatmap Grid */}
      <div style={{ display: 'flex', justifyContent: 'center', overflowX: 'auto', padding: '0.5rem 0' }}>
        <div style={{ display: 'inline-block', background: 'rgba(10, 16, 31, 0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '10px', padding: '1.25rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: `100px repeat(${TOKENS.length}, 46px)`, gap: '4px', alignItems: 'center' }}>
            {/* Top Column Token Headers */}
            <div style={{ fontSize: '0.7rem', color: '#64748B', fontWeight: 700 }}>Query \ Key</div>
            {TOKENS.map((token, colIdx) => (
              <div key={colIdx} style={{ fontSize: '0.72rem', color: '#38BDF8', fontWeight: 700, textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={token}>
                {token}
              </div>
            ))}

            {/* Matrix Rows */}
            {TOKENS.map((rowToken, rIdx) => (
              <React.Fragment key={rIdx}>
                {/* Row Header */}
                <div style={{ fontSize: '0.72rem', color: '#A78BFA', fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={rowToken}>
                  {rowToken}
                </div>

                {/* Heatmap Cells */}
                {TOKENS.map((_, cIdx) => {
                  const weight = currentMatrix[rIdx][cIdx];
                  const intensity = Math.min(1.0, weight * 1.3);
                  return (
                    <div
                      key={cIdx}
                      onMouseEnter={() => setHoveredCell({ i: rIdx, j: cIdx })}
                      onMouseLeave={() => setHoveredCell(null)}
                      style={{
                        width: '46px',
                        height: '42px',
                        borderRadius: '4px',
                        background: `rgba(139, 92, 246, ${Math.max(0.08, intensity)})`,
                        border: `1px solid ${hoveredCell?.i === rIdx && hoveredCell?.j === cIdx ? '#38BDF8' : 'rgba(139, 92, 246, 0.25)'}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '0.68rem',
                        fontWeight: 700,
                        color: intensity > 0.4 ? '#FFFFFF' : '#94A3B8',
                        cursor: 'pointer',
                        transition: 'transform 0.1s ease',
                        transform: hoveredCell?.i === rIdx && hoveredCell?.j === cIdx ? 'scale(1.15)' : 'scale(1)',
                        zIndex: hoveredCell?.i === rIdx && hoveredCell?.j === cIdx ? 10 : 1,
                      }}
                      title={`Query: "${rowToken}" attends to Key: "${TOKENS[cIdx]}" with weight ${weight.toFixed(3)}`}
                    >
                      {weight.toFixed(2)}
                    </div>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ── MAIN CONCEPTCANVAS3D EXPORT ──────────────────────────────────────────────
export const ConceptCanvas3D: React.FC<Concept3DProps> = ({
  conceptType = 'transformer_architecture',
  title,
  description: _description,
}) => {
  const mountRef = useRef<HTMLDivElement>(null);
  const fullscreenMountRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);

  // Active architecture model & studio view mode
  const [activeModel, setActiveModel] = useState<'transformer_architecture' | 'neural_network' | 'resnet50'>(
    conceptType === 'neural_network' ? 'neural_network' : 'transformer_architecture'
  );
  const [activeStudioMode, setActiveStudioMode] = useState<'3d_hologram' | 'compute_dag' | 'attention_heatmap'>('3d_hologram');

  const isTransformer = activeModel === 'transformer_architecture';
  const isResNet = activeModel === 'resnet50';
  const activeStages = isTransformer ? TRANSFORMER_STAGES : isResNet ? RESNET_STAGES : MLP_LAYERS;

  const [selectedLayer, setSelectedLayer] = useState<LayerMetadata | null>(activeStages[0]);
  const [activeNodeInfo, setActiveNodeInfo] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState<boolean>(true);
  const [activeCameraPreset, setActiveCameraPreset] = useState<'perspective' | 'front' | 'isometric'>('perspective');

  const firePulseRef = useRef<(() => void) | null>(null);
  const setCameraAngleRef = useRef<((mode: 'perspective' | 'front' | 'isometric') => void) | null>(null);

  // Sync selected layer when activeModel changes
  useEffect(() => {
    setSelectedLayer(activeStages[0]);
  }, [activeModel]);

  // Setup Three.js scene
  const setupThreeScene = (container: HTMLDivElement, isModal: boolean) => {
    const width = container.clientWidth || (isModal ? 800 : 400);
    const height = container.clientHeight || (isModal ? 540 : 290);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x050914);

    const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    camera.position.set(0, 0, isModal ? 21 : 18);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    // Lighting
    scene.add(new THREE.AmbientLight(0xffffff, 1.1));
    const cyanLight = new THREE.PointLight(0x38bdf8, 2.5, 80);
    cyanLight.position.set(16, 16, 16);
    scene.add(cyanLight);
    const purpleLight = new THREE.PointLight(0xa855f7, 2.2, 80);
    purpleLight.position.set(-16, -16, -16);
    scene.add(purpleLight);

    // Starfield
    const starCount = 200;
    const starGeo = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 65;
      starPositions[i + 1] = (Math.random() - 0.5) * 50;
      starPositions[i + 2] = (Math.random() - 0.5) * 45 - 12;
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x38bdf8, size: 0.18, transparent: true, opacity: 0.45 })));

    const mainGroup = new THREE.Group();
    scene.add(mainGroup);
    const interactiveObjects: THREE.Object3D[] = [];

    interface PulsePacket {
      mesh: THREE.Mesh;
      curve?: THREE.CubicBezierCurve3;
      p1?: THREE.Vector3;
      p2?: THREE.Vector3;
      progress: number;
      speed: number;
      isCurve: boolean;
    }
    const pulsePackets: PulsePacket[] = [];
    const pulseGeo = new THREE.SphereGeometry(0.12, 12, 12);
    const pulseMat = new THREE.MeshBasicMaterial({ color: 0xffffff });

    // ── A. TRANSFORMER ARCHITECTURE ─────────────────────────────────────────
    if (isTransformer) {
      const inputX = -7.0;
      const inputSprite = createTextSprite('INPUT EMBEDDINGS', 'Tokens + Positional Encoding (E+P)', '#10B981');
      inputSprite.position.set(inputX, 4.4, 0);
      mainGroup.add(inputSprite);

      const tokenNames = ['Token "The"', 'Token "Library"', 'Token "AI"'];
      const tokenPositions: THREE.Vector3[] = [];
      const tokenGeo = new THREE.CylinderGeometry(0.5, 0.5, 0.4, 20);
      const tokenMat = new THREE.MeshPhongMaterial({ color: 0x10b981, emissive: 0x059669, emissiveIntensity: 0.5 });

      tokenNames.forEach((name, i) => {
        const y = (i - 1) * 2.2;
        const pos = new THREE.Vector3(inputX, y, 0);
        tokenPositions.push(pos);
        const mesh = new THREE.Mesh(tokenGeo, tokenMat);
        mesh.position.copy(pos);
        mesh.rotation.x = Math.PI / 2;
        mesh.userData = { label: `${name} (768-dim Embedding Vector)`, meta: TRANSFORMER_STAGES[0] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // Attention Module (x = -3.2)
      const mhaX = -3.2;
      const mhaSprite = createTextSprite('MULTI-HEAD ATTENTION', '8 Parallel Heads (Q, K, V)', '#8B5CF6');
      mhaSprite.position.set(mhaX, 4.4, 0);
      mainGroup.add(mhaSprite);

      const qkvLabels = [
        { label: 'Query Projection (Q)', color: 0xf59e0b, y: 1.6 },
        { label: 'Key Projection (K)', color: 0x38bdf8, y: 0.0 },
        { label: 'Value Projection (V)', color: 0xa855f7, y: -1.6 },
      ];
      const qkvPositions: THREE.Vector3[] = [];
      qkvLabels.forEach((qkv) => {
        const pos = new THREE.Vector3(mhaX - 1.2, qkv.y, 0);
        qkvPositions.push(pos);
        const mesh = new THREE.Mesh(new THREE.SphereGeometry(0.42, 20, 20), new THREE.MeshPhongMaterial({ color: qkv.color, emissive: qkv.color, emissiveIntensity: 0.4 }));
        mesh.position.copy(pos);
        mesh.userData = { label: `${qkv.label} Matrix`, meta: TRANSFORMER_STAGES[1] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // 4 Parallel Attention Heads
      const headZCoords = [-1.8, -0.6, 0.6, 1.8];
      const headPositions: THREE.Vector3[] = [];
      headZCoords.forEach((z, hIdx) => {
        const hPos = new THREE.Vector3(mhaX + 1.2, 0, z);
        headPositions.push(hPos);
        const hMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 1.4, 16), new THREE.MeshPhongMaterial({ color: 0x8b5cf6, emissive: 0x6d28d9, emissiveIntensity: 0.5, transparent: true, opacity: 0.9 }));
        hMesh.position.copy(hPos);
        hMesh.userData = { label: `Attention Head ${hIdx + 1}/8 (d_k = 64)`, meta: TRANSFORMER_STAGES[1] };
        mainGroup.add(hMesh);
        interactiveObjects.push(hMesh);

        qkvPositions.forEach((qPos) => {
          const lGeo = new THREE.BufferGeometry().setFromPoints([qPos, hPos]);
          mainGroup.add(new THREE.Line(lGeo, new THREE.LineBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0.35 })));
        });
      });

      // Add & LayerNorm Slab 1 (x = 0.5)
      const norm1X = 0.5;
      const norm1Mesh = new THREE.Mesh(new THREE.BoxGeometry(0.5, 4.4, 2.4), new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.35, transparent: true, opacity: 0.85 }));
      norm1Mesh.position.set(norm1X, 0, 0);
      norm1Mesh.userData = { label: 'Add & LayerNorm 1: LayerNorm(x + Attention(x))', meta: TRANSFORMER_STAGES[2] };
      mainGroup.add(norm1Mesh);
      interactiveObjects.push(norm1Mesh);

      // Curved Residual Skip Highway looping over attention block
      tokenPositions.forEach((tPos) => {
        const p0 = tPos.clone();
        const p1 = new THREE.Vector3((inputX + norm1X) / 2, 4.2, 2.5);
        const p2 = new THREE.Vector3((inputX + norm1X) / 2, 4.2, -2.5);
        const p3 = new THREE.Vector3(norm1X, tPos.y, 0);
        const curve = new THREE.CubicBezierCurve3(p0, p1, p2, p3);
        const tubeMesh = new THREE.Mesh(new THREE.TubeGeometry(curve, 32, 0.08, 8, false), new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.8 }));
        mainGroup.add(tubeMesh);

        const pMesh = new THREE.Mesh(pulseGeo, pulseMat);
        mainGroup.add(pMesh);
        pulsePackets.push({ mesh: pMesh, curve, progress: Math.random(), speed: 0.012, isCurve: true });
      });

      // Position-Wise FFN (x = 4.0)
      const ffnX = 4.0;
      const ffnSprite = createTextSprite('FEED-FORWARD NETWORK', 'Position-Wise FFN (d_ff = 3072)', '#EC4899');
      ffnSprite.position.set(ffnX, 4.4, 0);
      mainGroup.add(ffnSprite);

      const ffnY = [1.8, 0.6, -0.6, -1.8];
      const ffnPositions: THREE.Vector3[] = [];
      ffnY.forEach((y, i) => {
        const pos = new THREE.Vector3(ffnX, y, 0);
        ffnPositions.push(pos);
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 0.7), new THREE.MeshPhongMaterial({ color: 0xec4899, emissive: 0xdb2777, emissiveIntensity: 0.4 }));
        mesh.position.copy(pos);
        mesh.userData = { label: `FFN Dense Unit ${i + 1} (GELU Non-Linearity)`, meta: TRANSFORMER_STAGES[3] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // Add & LayerNorm Slab 2 (x = 6.2)
      const norm2X = 6.2;
      const norm2Mesh = new THREE.Mesh(new THREE.BoxGeometry(0.5, 4.4, 2.4), new THREE.MeshPhongMaterial({ color: 0xec4899, emissive: 0x9d174d, emissiveIntensity: 0.3, transparent: true, opacity: 0.85 }));
      norm2Mesh.position.set(norm2X, 0, 0);
      norm2Mesh.userData = { label: 'Add & LayerNorm 2: LayerNorm(x\' + FFN(x\'))', meta: TRANSFORMER_STAGES[2] };
      mainGroup.add(norm2Mesh);
      interactiveObjects.push(norm2Mesh);

      // Output Softmax Logits (x = 8.5)
      const outX = 8.5;
      const outSprite = createTextSprite('SOFTMAX LOGITS', 'P(w_t | w_<t) Vocabulary Distribution', '#F59E0B');
      outSprite.position.set(outX, 4.4, 0);
      mainGroup.add(outSprite);

      const probHeights = [2.2, 1.4, 0.7];
      const probLabels = ['Logit: "model" (P=0.68)', 'Logit: "system" (P=0.22)', 'Logit: "book" (P=0.10)'];
      probHeights.forEach((h, i) => {
        const y = (i - 1) * 2.0;
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.6, h, 0.6), new THREE.MeshPhongMaterial({ color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.5 }));
        mesh.position.set(outX, y, 0);
        mesh.userData = { label: probLabels[i], meta: TRANSFORMER_STAGES[4] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      firePulseRef.current = () => {
        pulsePackets.forEach((p) => { p.progress = 0; p.speed = 0.024; });
      };
    }

    // ── B. RESNET-50 ARCHITECTURE ───────────────────────────────────────────
    else if (isResNet) {
      const resnetX = [-6.0, -3.0, 0.5, 4.0, 7.5];
      const slabSizes = [
        { w: 0.5, h: 4.8, d: 4.8, c: 0x10b981, label: 'Conv1 (224x224x3 -> 112x112x64)' },
        { w: 0.5, h: 3.8, d: 3.8, c: 0x38bdf8, label: 'BatchNorm & MaxPool (56x56x64)' },
        { w: 0.6, h: 3.0, d: 3.0, c: 0x8b5cf6, label: 'Residual Bottleneck Block (56x56x256)' },
        { w: 0.6, h: 1.5, d: 1.5, c: 0xec4899, label: 'Global Average Pool (1x1x2048)' },
        { w: 0.6, h: 2.5, d: 0.8, c: 0xf59e0b, label: 'Linear 1000 Class Logits' },
      ];

      slabSizes.forEach((slab, sIdx) => {
        const x = resnetX[sIdx];
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(slab.w, slab.h, slab.d), new THREE.MeshPhongMaterial({ color: slab.c, emissive: slab.c, emissiveIntensity: 0.4, transparent: true, opacity: 0.85 }));
        mesh.position.set(x, 0, 0);
        mesh.userData = { label: slab.label, meta: RESNET_STAGES[sIdx] };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);

        const sprite = createTextSprite(RESNET_STAGES[sIdx].shortName, RESNET_STAGES[sIdx].role, RESNET_STAGES[sIdx].color);
        sprite.position.set(x, 3.8, 0);
        mainGroup.add(sprite);

        if (sIdx < slabSizes.length - 1) {
          const nextX = resnetX[sIdx + 1];
          const lGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, 0, 0), new THREE.Vector3(nextX, 0, 0)]);
          mainGroup.add(new THREE.Line(lGeo, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.3 })));
        }
      });

      // Curved Identity Skip connection looping around bottleneck
      const curve = new THREE.CubicBezierCurve3(
        new THREE.Vector3(resnetX[1], 0, 1.8),
        new THREE.Vector3((resnetX[1] + resnetX[2]) / 2, 3.2, 2.5),
        new THREE.Vector3((resnetX[1] + resnetX[2]) / 2, 3.2, -2.5),
        new THREE.Vector3(resnetX[2], 0, 0)
      );
      mainGroup.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 32, 0.08, 8, false), new THREE.MeshPhongMaterial({ color: 0x8b5cf6, emissive: 0x6d28d9, emissiveIntensity: 0.8 })));
    }

    // ── C. MULTI-LAYER PERCEPTRON (MLP) ─────────────────────────────────────
    else {
      const layerCounts = [3, 4, 4, 2];
      const layerSpacing = 3.9;
      const nodeSpacing = 2.2;
      const nodePositions: THREE.Vector3[][] = [];

      MLP_LAYERS.forEach((meta, lIdx) => {
        const count = layerCounts[lIdx];
        const layerNodes: THREE.Vector3[] = [];
        const x = (lIdx - (layerCounts.length - 1) / 2) * layerSpacing;

        const headerSprite = createTextSprite(meta.shortName, meta.role, meta.color);
        headerSprite.position.set(x, 4.4, 0);
        mainGroup.add(headerSprite);

        for (let i = 0; i < count; i++) {
          const y = (i - (count - 1) / 2) * nodeSpacing;
          const pos = new THREE.Vector3(x, y, 0);
          layerNodes.push(pos);

          const nodeMesh = new THREE.Mesh(new THREE.SphereGeometry(0.42, 24, 24), new THREE.MeshPhongMaterial({ color: meta.hexColor, emissive: meta.hexColor, emissiveIntensity: 0.45, shininess: 95 }));
          nodeMesh.position.copy(pos);
          nodeMesh.userData = { label: `${meta.title} (Neuron ${i + 1}/${count})`, meta };
          mainGroup.add(nodeMesh);
          interactiveObjects.push(nodeMesh);
        }
        nodePositions.push(layerNodes);
      });

      // Synapse Connections
      for (let l = 0; l < nodePositions.length - 1; l++) {
        const currentLayer = nodePositions[l];
        const nextLayer = nodePositions[l + 1];
        currentLayer.forEach((p1) => {
          nextLayer.forEach((p2) => {
            const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints([p1, p2]), new THREE.LineBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.15 }));
            mainGroup.add(line);
          });
        });
      }
    }

    // Camera presets
    setCameraAngleRef.current = (mode) => {
      setActiveCameraPreset(mode);
      if (mode === 'front') camera.position.set(0, 0, isModal ? 21 : 18);
      else if (mode === 'isometric') camera.position.set(15, 12, 18);
      else camera.position.set(0, 3, isModal ? 21 : 18);
      camera.lookAt(0, 0, 0);
    };

    // Animation Loop
    let animId: number;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      if (isRotating) mainGroup.rotation.y += 0.0035;
      pulsePackets.forEach((p) => {
        p.progress += p.speed;
        if (p.progress > 1) p.progress = 0;
        if (p.isCurve && p.curve) p.mesh.position.copy(p.curve.getPoint(p.progress));
      });
      renderer.render(scene, camera);
    };
    animate();

    // Raycaster & Mouse Interaction (Orbiting & Raycasting)
    let isDragging = false;
    let prevMouseX = 0;
    let prevMouseY = 0;
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const onClick = (e: MouseEvent) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveObjects);
      if (intersects.length > 0) {
        const hit = intersects[0].object;
        if (hit.userData?.label) {
          setActiveNodeInfo(hit.userData.label);
        }
        if (hit.userData?.meta) {
          setSelectedLayer(hit.userData.meta);
        }
      }
    };

    const onMouseDown = (e: MouseEvent) => { isDragging = true; prevMouseX = e.clientX; prevMouseY = e.clientY; };
    const onMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        const deltaX = e.clientX - prevMouseX;
        const deltaY = e.clientY - prevMouseY;
        mainGroup.rotation.y += deltaX * 0.008;
        mainGroup.rotation.x += deltaY * 0.008;
        prevMouseX = e.clientX;
        prevMouseY = e.clientY;
      }
    };
    const onMouseUp = () => { isDragging = false; };
    container.addEventListener('click', onClick);
    container.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);

    return () => {
      cancelAnimationFrame(animId);
      container.removeEventListener('click', onClick);
      container.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      if (renderer.domElement.parentElement) renderer.domElement.parentElement.removeChild(renderer.domElement);
      renderer.dispose();
    };
  };

  // Re-build 3D scene on container mount, fullscreen toggle, or activeModel change
  useEffect(() => {
    if (activeStudioMode !== '3d_hologram') return;
    const container = isFullscreen ? fullscreenMountRef.current : mountRef.current;
    if (!container) return;
    const cleanup = setupThreeScene(container, isFullscreen);
    return cleanup;
  }, [isFullscreen, activeModel, activeStudioMode]);

  return (
    <>
      {/* ── 1. INLINE CARD (COPILOT DRAWER VIEW) ────────────────────────────── */}
      <div
        style={{
          borderRadius: '12px',
          overflow: 'hidden',
          border: '1px solid rgba(56, 189, 248, 0.35)',
          background: '#070D1B',
          marginTop: '0.75rem',
          marginBottom: '0.75rem',
          boxShadow: '0 12px 32px rgba(0, 0, 0, 0.55)',
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0.55rem 0.85rem',
            background: 'linear-gradient(90deg, rgba(14, 22, 38, 0.98), rgba(8, 13, 26, 0.98))',
            borderBottom: '1px solid rgba(56, 189, 248, 0.2)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
            <span style={{ fontSize: '1.05rem' }}>🪐</span>
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#38BDF8', letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                {title || (isTransformer ? 'TRANSFORMER & ATTENTION ARCHITECTURE' : isResNet ? 'RESNET-50 CONVNET' : 'MULTI-LAYER PERCEPTRON')}
              </div>
              <div style={{ fontSize: '0.62rem', color: '#64748B' }}>
                Industry 3D WebGL Engine · Netron DAG · Attention Heatmaps
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <button
              type="button"
              onClick={() => setIsFullscreen(true)}
              style={{
                fontSize: '0.72rem',
                padding: '0.3rem 0.75rem',
                borderRadius: '6px',
                border: '1px solid rgba(56, 189, 248, 0.45)',
                background: 'linear-gradient(135deg, rgba(56, 189, 248, 0.25), rgba(139, 92, 246, 0.25))',
                color: '#38BDF8',
                cursor: 'pointer',
                fontWeight: 600,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                boxShadow: '0 2px 8px rgba(56, 189, 248, 0.25)',
              }}
              title="Open full-screen industry evaluation sandbox"
            >
              <span>⛶</span> Fullscreen Studio
            </button>
          </div>
        </div>

        {/* Small Inline 3D Canvas */}
        <div ref={mountRef} style={{ width: '100%', height: '240px', position: 'relative', cursor: 'grab' }} />
      </div>

      {/* ── 2. FULLSCREEN INDUSTRY ARCHITECTURAL STUDIO MODAL ───────────────── */}
      {isFullscreen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 99999,
            background: 'rgba(3, 7, 18, 0.96)',
            backdropFilter: 'blur(16px)',
            display: 'flex',
            flexDirection: 'column',
            padding: '1rem',
            animation: 'fadeIn 0.2s ease',
          }}
        >
          {/* Header Bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.75rem 1.25rem',
              background: 'linear-gradient(90deg, #0b1224, #080d1a)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '12px 12px 0 0',
              flexWrap: 'wrap',
              gap: '0.75rem',
            }}
          >
            {/* Title & Architecture Selector */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#F8FAFC', margin: 0 }}>
                  Neural Architecture Evaluation Studio
                </h2>
                <div style={{ fontSize: '0.72rem', color: '#64748B' }}>
                  Industry-Grade Compute Graph · Volumetric Three.js · Self-Attention Heatmap
                </div>
              </div>

              {/* Architecture Preset Buttons */}
              <div style={{ display: 'flex', gap: '0.35rem', background: 'rgba(255, 255, 255, 0.05)', padding: '3px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                <button
                  type="button"
                  onClick={() => setActiveModel('transformer_architecture')}
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: activeModel === 'transformer_architecture' ? '#8B5CF6' : 'transparent',
                    color: activeModel === 'transformer_architecture' ? '#FFFFFF' : '#94A3B8',
                    cursor: 'pointer',
                  }}
                >
                  ⚡ Transformer (GPT/BERT)
                </button>
                <button
                  type="button"
                  onClick={() => setActiveModel('neural_network')}
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: activeModel === 'neural_network' ? '#38BDF8' : 'transparent',
                    color: activeModel === 'neural_network' ? '#040711' : '#94A3B8',
                    cursor: 'pointer',
                  }}
                >
                  🧠 Deep MLP
                </button>
                <button
                  type="button"
                  onClick={() => setActiveModel('resnet50')}
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: activeModel === 'resnet50' ? '#10B981' : 'transparent',
                    color: activeModel === 'resnet50' ? '#040711' : '#94A3B8',
                    cursor: 'pointer',
                  }}
                >
                  🖼️ ResNet-50 (CNN)
                </button>
              </div>
            </div>

            {/* Studio View Mode Switcher */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <div style={{ display: 'flex', gap: '0.35rem', background: 'rgba(255, 255, 255, 0.05)', padding: '3px', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.1)' }}>
                <button
                  type="button"
                  onClick={() => setActiveStudioMode('3d_hologram')}
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: activeStudioMode === '3d_hologram' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                    color: activeStudioMode === '3d_hologram' ? '#38BDF8' : '#94A3B8',
                    cursor: 'pointer',
                  }}
                >
                  🪐 3D Volumetric Lab
                </button>
                <button
                  type="button"
                  onClick={() => setActiveStudioMode('compute_dag')}
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    padding: '0.35rem 0.75rem',
                    borderRadius: '6px',
                    border: 'none',
                    background: activeStudioMode === 'compute_dag' ? 'rgba(56, 189, 248, 0.25)' : 'transparent',
                    color: activeStudioMode === 'compute_dag' ? '#38BDF8' : '#94A3B8',
                    cursor: 'pointer',
                  }}
                >
                  📊 Compute DAG (Netron)
                </button>
                {activeModel === 'transformer_architecture' && (
                  <button
                    type="button"
                    onClick={() => setActiveStudioMode('attention_heatmap')}
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: 700,
                      padding: '0.35rem 0.75rem',
                      borderRadius: '6px',
                      border: 'none',
                      background: activeStudioMode === 'attention_heatmap' ? 'rgba(139, 92, 246, 0.3)' : 'transparent',
                      color: activeStudioMode === 'attention_heatmap' ? '#A78BFA' : '#94A3B8',
                      cursor: 'pointer',
                    }}
                  >
                    🔥 Attention Heatmap
                  </button>
                )}
              </div>

              {activeStudioMode === '3d_hologram' && (
                <>
                  <button
                    type="button"
                    onClick={() => firePulseRef.current?.()}
                    style={{
                      fontSize: '0.75rem',
                      padding: '0.35rem 0.75rem',
                      borderRadius: '6px',
                      border: '1px solid rgba(245, 158, 11, 0.5)',
                      background: 'rgba(245, 158, 11, 0.2)',
                      color: '#F59E0B',
                      cursor: 'pointer',
                      fontWeight: 700,
                    }}
                  >
                    ⚡ Forward Pass
                  </button>
                  <div style={{ display: 'flex', gap: '0.2rem', background: 'rgba(255, 255, 255, 0.05)', padding: '2px', borderRadius: '6px' }}>
                    {(['perspective', 'front', 'isometric'] as const).map((cam) => (
                      <button
                        key={cam}
                        type="button"
                        onClick={() => setCameraAngleRef.current?.(cam)}
                        style={{
                          fontSize: '0.7rem',
                          padding: '0.25rem 0.5rem',
                          borderRadius: '4px',
                          border: 'none',
                          background: activeCameraPreset === cam ? 'rgba(56, 189, 248, 0.3)' : 'transparent',
                          color: activeCameraPreset === cam ? '#38BDF8' : '#94A3B8',
                          cursor: 'pointer',
                          textTransform: 'capitalize',
                        }}
                      >
                        {cam}
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsRotating((p) => !p)}
                    style={{
                      fontSize: '0.75rem',
                      padding: '0.35rem 0.65rem',
                      borderRadius: '6px',
                      border: '1px solid rgba(255, 255, 255, 0.2)',
                      background: isRotating ? 'rgba(56, 189, 248, 0.2)' : 'transparent',
                      color: isRotating ? '#38BDF8' : '#94A3B8',
                      cursor: 'pointer',
                    }}
                  >
                    {isRotating ? '🔄 Rotate ON' : '⏸️ Paused'}
                  </button>
                </>
              )}

              <button
                type="button"
                onClick={() => setIsFullscreen(false)}
                style={{
                  fontSize: '0.78rem',
                  padding: '0.35rem 0.85rem',
                  borderRadius: '6px',
                  border: '1px solid rgba(239, 68, 68, 0.45)',
                  background: 'rgba(239, 68, 68, 0.18)',
                  color: '#F87171',
                  cursor: 'pointer',
                  fontWeight: 700,
                }}
              >
                ✕ Close (Esc)
              </button>
            </div>
          </div>

          {/* Body: Viewport + Inspector */}
          <div style={{ flex: 1, display: 'flex', border: '1px solid rgba(56, 189, 248, 0.25)', borderTop: 'none', borderRadius: '0 0 12px 12px', overflow: 'hidden', background: '#040711' }}>
            {/* Viewport: 3D Hologram, Compute DAG, or Attention Heatmap */}
            {activeStudioMode === '3d_hologram' && (
              <div ref={fullscreenMountRef} style={{ flex: 1, position: 'relative', cursor: 'grab', height: '100%' }}>
                <div style={{ position: 'absolute', top: '16px', left: '16px', background: 'rgba(8, 13, 26, 0.88)', border: '1px solid rgba(255, 255, 255, 0.12)', borderRadius: '8px', padding: '8px 14px', color: '#94A3B8', fontSize: '0.75rem', pointerEvents: 'none' }}>
                  🖱️ Left Click & Drag to Orbit · Scroll to Zoom · Arched Glowing Tubes = Residual Skip Connections (Add & Norm)
                </div>
                {activeNodeInfo && (
                  <div style={{ position: 'absolute', bottom: '24px', left: '50%', transform: 'translateX(-50%)', background: 'rgba(15, 23, 42, 0.96)', border: '1px solid #38BDF8', borderRadius: '8px', padding: '8px 22px', color: '#38BDF8', fontSize: '0.85rem', fontWeight: 600 }}>
                    🎯 Selected: {activeNodeInfo}
                  </div>
                )}
              </div>
            )}

            {activeStudioMode === 'compute_dag' && (
              <ComputeDAGView
                modelType={activeModel}
                selectedLayerId={selectedLayer?.id || null}
                onSelectLayer={(l) => setSelectedLayer(l)}
              />
            )}

            {activeStudioMode === 'attention_heatmap' && (
              <AttentionHeatmapView />
            )}

            {/* Right 30%: Layer Inspector & Defense Card */}
            <div style={{ width: '380px', borderLeft: '1px solid rgba(56, 189, 248, 0.2)', background: 'rgba(10, 16, 31, 0.98)', display: 'flex', flexDirection: 'column', overflowY: 'auto', padding: '1.25rem', gap: '1.25rem' }}>
              {selectedLayer ? (
                <div style={{ background: 'rgba(15, 23, 42, 0.95)', border: `1px solid ${selectedLayer.color}`, borderRadius: '10px', padding: '1.1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: selectedLayer.color, boxShadow: `0 0 10px ${selectedLayer.color}` }} />
                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: selectedLayer.color, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {selectedLayer.role}
                    </span>
                  </div>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#F8FAFC', margin: '0 0 0.5rem 0' }}>
                    {selectedLayer.title}
                  </h3>
                  <div style={{ background: 'rgba(6, 10, 23, 0.95)', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid rgba(255, 255, 255, 0.08)', marginBottom: '0.75rem' }}>
                    <div style={{ fontSize: '0.65rem', color: '#64748B', marginBottom: '3px' }}>MATHEMATICAL FORMULATION:</div>
                    <code style={{ fontSize: '0.78rem', color: '#38BDF8', wordBreak: 'break-all', fontWeight: 600 }}>
                      {selectedLayer.math}
                    </code>
                  </div>
                  {selectedLayer.tensorShape && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: '#94A3B8', marginBottom: '0.5rem' }}>
                      <span>Tensor Shape:</span>
                      <strong style={{ color: '#38BDF8' }}>{selectedLayer.tensorShape}</strong>
                    </div>
                  )}
                  {selectedLayer.params && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: '#94A3B8', marginBottom: '0.75rem' }}>
                      <span>Parameters:</span>
                      <strong style={{ color: '#F59E0B' }}>{selectedLayer.params}</strong>
                    </div>
                  )}
                  <p style={{ fontSize: '0.8rem', color: '#CBD5E1', lineHeight: 1.55, margin: 0 }}>
                    {selectedLayer.details}
                  </p>
                </div>
              ) : (
                <div style={{ padding: '1rem', border: '1px dashed rgba(255, 255, 255, 0.15)', borderRadius: '10px', textAlign: 'center', color: '#64748B', fontSize: '0.8rem' }}>
                  Click any layer block in the 3D canvas or Compute DAG to inspect its parameters.
                </div>
              )}

              {/* Step-by-Step Architecture Pipeline */}
              {activeStages.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.82rem', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.04em', margin: '0 0 0.65rem 0' }}>
                    {isTransformer ? 'Transformer Encoder Layers' : isResNet ? 'ResNet Bottleneck Stages' : 'Perceptron Layers'}
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                    {activeStages.map((layer, idx) => (
                      <div
                        key={layer.id}
                        onClick={() => setSelectedLayer(layer)}
                        style={{
                          padding: '0.7rem 0.9rem',
                          borderRadius: '8px',
                          background: selectedLayer?.id === layer.id ? 'rgba(56, 189, 248, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                          border: `1px solid ${selectedLayer?.id === layer.id ? layer.color : 'rgba(255, 255, 255, 0.06)'}`,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.75rem',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        <div style={{ width: '26px', height: '26px', borderRadius: '50%', background: `${layer.color}25`, border: `1px solid ${layer.color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700, color: layer.color, flexShrink: 0 }}>
                          {idx + 1}
                        </div>
                        <div style={{ overflow: 'hidden' }}>
                          <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#F1F5F9' }}>
                            {layer.shortName}
                          </div>
                          <div style={{ fontSize: '0.65rem', color: '#64748B' }}>
                            {layer.role}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Academic Teacher Defense Card */}
              <div style={{ marginTop: 'auto', padding: '0.9rem', borderRadius: '8px', background: 'rgba(56, 189, 248, 0.05)', border: '1px solid rgba(56, 189, 248, 0.18)', fontSize: '0.75rem', color: '#94A3B8', lineHeight: 1.5 }}>
                🎓 <strong style={{ color: '#38BDF8' }}>Teacher Defense Note:</strong> In Vaswani et al. (2017), Multi-Head Attention calculates all pairwise token context dot-products in parallel (d_k = 64, h = 8). Residual skip-connections (Add & LayerNorm) ensure stable gradient flow, entirely bypassing the sequential latency bottleneck of RNNs and LSTMs.
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
