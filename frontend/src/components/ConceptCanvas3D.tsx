import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';

export interface Concept3DProps {
  conceptType?: 'transformer_architecture' | 'neural_network' | 'distributed_cluster' | 'molecule' | 'quantum_bloch' | 'generic';
  title?: string;
  description?: string;
}

export interface LayerMetadata {
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
  pytorchCode?: string;
  plainEnglish: string;
  toyExample: {
    inputDesc: string;
    computation: string;
    outputDesc: string;
    insight: string;
  };
  defenseQA: {
    question: string;
    answer: string;
  }[];
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
    pytorchCode: 'x = self.token_embed(tokens) + self.pos_embed[:, :seq_len]',
    plainEnglish: 'The Library Catalog Card Index: When a patron enters a query like "Students read books", the neural network cannot read raw English text. It looks up each word in a 30,522-word vocabulary table to fetch a 768-dimensional semantic fingerprint (embedding). Because Transformers process all words simultaneously in parallel rather than sequentially left-to-right, we superimpose a unique sinusoidal frequency wave onto each word so the model knows who came first without any sequential bottleneck.',
    toyExample: {
      inputDesc: 'Query Tokens: ["Students", "read", "books"]',
      computation: 'Embedding("Students") = [0.82, -0.41, 0.15] + SinusoidalPE(pos=0) = [0.00, 1.00, 0.00]',
      outputDesc: 'Combined Input Vector z_0 = [0.82, 0.59, 0.15]',
      insight: 'Words are now points in a 768-dim geometric space where semantic neighbors ("books", "library") cluster naturally together while retaining exact order.',
    },
    defenseQA: [
      {
        question: 'Why do Transformers require Positional Encoding while RNNs and LSTMs do not?',
        answer: 'Self-attention is mathematically permutation-invariant: swapping word positions produces identical attention matrices without positional encoding. Recurrent networks inherently inject order via step-by-step hidden states (h_t = f(h_{t-1}, x_t)), but this creates an O(N) sequential bottleneck. Sinusoidal positional encodings enable 100% parallel matrix multiplication on GPUs while allowing the model to extrapolate to arbitrary sequence lengths via linear transformations PE(pos+k).',
      },
      {
        question: 'Why add positional encodings to token embeddings rather than concatenating them?',
        answer: 'Concatenation would increase the embedding dimension by 50-100%, inflating every weight matrix throughout all 12-32 attention layers. Adding preserves the dimension d_model=768. Because high-dimensional vector spaces are largely orthogonal, semantic information and positional signals coexist without destructive interference.',
      },
    ],
  },
  {
    id: 'stage-attention',
    title: 'Multi-Head Self-Attention Module (8 Parallel Heads)',
    shortName: 'Multi-Head Attention (Q,K,V)',
    color: '#8B5CF6',
    hexColor: 0x8b5cf6,
    math: 'Attention(Q,K,V) = softmax(Q K^T / sqrt(d_k)) V',
    role: 'Parallel Context Heads',
    details: 'Splits representations into 8 parallel attention heads across Query (Q), Key (K), and Value (V) projections. Calculates pairwise token affinity dot-products simultaneously in O(1) sequential operations.',
    tensorShape: '[B, 8, 512, 64]',
    params: '2.36M Params (4 x 768 x 768)',
    flops: '7.08 GFLOPs',
    pytorchCode: 'scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(d_k)\nattn = F.softmax(scores, dim=-1)\nout = torch.matmul(attn, V)',
    plainEnglish: 'The Research Librarian Desk: When a student asks for information: Query (Q) is the student\'s question; Key (K) is the index tags on library shelves; Value (V) is the actual content inside the books on those shelves. The model calculates the dot-product affinity between the Query and every Key to determine relevance weights. Multi-Head means having 8 specialized librarians working simultaneously: one tracks grammatical syntax (verbs to nouns), another tracks coreferences ("it" -> "the book"), and another tracks topical context.',
    toyExample: {
      inputDesc: 'Query for token "read": q = [1.2, 0.4]. Keys: k_Students = [0.9, 0.2], k_books = [1.1, 0.5]',
      computation: 'Raw dot-products: q·k_Students = 1.16 | q·k_books = 1.52. Scale by sqrt(d_k)=8: [0.145, 0.190]. Softmax: [0.489, 0.511]',
      outputDesc: 'Contextual Vector = 0.489 * v_Students + 0.511 * v_books',
      insight: 'The word "read" dynamically absorbs context from both the subject ("Students") and object ("books") in a single parallel operation!',
    },
    defenseQA: [
      {
        question: 'Why do we divide by sqrt(d_k) in the scaled dot-product attention formula?',
        answer: 'For large values of d_k (e.g. 64), the variance of the dot product q·k = sum(q_i * k_i) grows proportionally to d_k. Large dot products push the Softmax function into saturation regions with near-zero gradients (vanishing gradient problem). Dividing by sqrt(d_k) normalizes the variance back to 1.0, preserving healthy gradient flow during backpropagation.',
      },
      {
        question: 'Why is Multi-Head Attention superior to a single large attention head?',
        answer: 'A single attention head can only compute one weighted average representation across positions. Multi-Head Attention projects Queries, Keys, and Values into h=8 distinct subspaces of dimension d_k = d_model / h = 64. This allows the model to simultaneously attend to syntactic relations, semantic coreferences, and long-range dependencies across multiple positions without increasing computational complexity.',
      },
    ],
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
    pytorchCode: 'x = self.norm1(x + self.attn(x))  # Pre-LN: x = x + self.attn(self.norm1(x))',
    plainEnglish: 'The Express Bypass Highway: Imagine a student\'s research paper passing through an editor. Instead of replacing the student\'s original draft entirely, the editor writes annotations on sticky notes and attaches them (x + Sublayer(x)). The original ideas are never lost or corrupted. LayerNorm then recalibrates the variance so no single paragraph is overwhelmingly loud or quiet.',
    toyExample: {
      inputDesc: 'Input vector x = [2.10, -0.90, 3.20]. Attention delta F(x) = [0.25, 0.45, -0.15]',
      computation: 'Residual Sum: x + F(x) = [2.35, -0.45, 3.05]. Mean μ = 1.65, Std σ = 1.51. Normalized: (val - μ) / σ',
      outputDesc: 'LayerNorm Output = [0.46, -1.39, 0.93] (Zero mean, unit variance)',
      insight: 'The original token identity is preserved, and activations are strictly bounded to prevent exploding signals.',
    },
    defenseQA: [
      {
        question: 'How do residual skip connections solve the vanishing gradient problem in deep networks?',
        answer: 'By defining y = x + F(x), the gradient with respect to input x during backpropagation is d(y)/dx = 1 + d(F(x))/dx. The constant "1" term creates an uninterrupted highway where gradient signals propagate backwards directly through dozens of layers without decaying, even if the sublayer weights produce tiny gradients.',
      },
      {
        question: 'What is the key difference between Layer Normalization and Batch Normalization?',
        answer: 'Batch Normalization normalizes across the batch dimension (which fails on small batch sizes or variable-length NLP sequences). Layer Normalization normalizes across feature dimensions independently for each individual token, making it completely independent of batch size and ideal for sequence generation and distributed inference.',
      },
    ],
  },
  {
    id: 'stage-ffn',
    title: 'Position-Wise Feed-Forward Network (FFN)',
    shortName: 'Feed-Forward [FFN]',
    color: '#EC4899',
    hexColor: 0xec4899,
    math: 'FFN(x\') = GELU(x\' W_1 + b_1) W_2 + b_2',
    role: 'Non-Linear Abstraction',
    details: 'Dense two-layer expansion (typically 4x d_model = 3072-dim) with GELU activation applied identically to each token position individually, followed by a secondary residual skip connection.',
    tensorShape: '[B, 512, 3072]',
    params: '4.72M Params (2 x 768 x 3072)',
    flops: '9.44 GFLOPs',
    pytorchCode: 'x = self.norm2(x + self.w2(F.gelu(self.w1(x))))',
    plainEnglish: 'The Encyclopedia Fact Retrieval: While Self-Attention shared information across different words in the sentence, the FFN examines each token individually in isolation. It expands the 768 dimensions up to 3,072 dimensions (a 4x explosion), passes them through a non-linear GELU activation gate, and compresses back down. Academic research (Geva et al., 2020) proves this layer acts as the model\'s factual knowledge memory bank, storing facts like "Athenaeum is a library".',
    toyExample: {
      inputDesc: 'Token vector h ∈ ℝ^768 for "books"',
      computation: 'W_1 projects 768 → 3072 dims. GELU activation: z * Φ(z). W_2 compresses 3072 → 768 dims',
      outputDesc: 'Enriched Concept Vector h_ffn ∈ ℝ^768 containing domain factual knowledge',
      insight: 'The 3,072 intermediate neurons act as pattern detectors, and the second matrix retrieves corresponding semantic attributes!',
    },
    defenseQA: [
      {
        question: 'Why is the hidden dimension of the FFN 4x larger than d_model?',
        answer: 'Self-attention performs linear routing of tokens, but high-order reasoning requires non-linear representational capacity. Expanding to 4 * d_model allows the network to project into an overcomplete basis where overlapping semantic attributes can be separated and activated independently by non-linear units.',
      },
      {
        question: 'Why do modern LLMs (GPT-4, LLaMA) prefer GELU / SwiGLU over standard ReLU?',
        answer: 'Standard ReLU sets all negative values to zero (max(0, x)), causing "dying neurons" that permanently lose gradients. GELU (Gaussian Error Linear Unit) scales the input by the cumulative Gaussian distribution, providing smooth differentiability and allowing small negative activations to retain gradient flow.',
      },
    ],
  },
  {
    id: 'stage-output',
    title: 'Linear Unembedding & Softmax Vocabulary Logits',
    shortName: 'Softmax Vocabulary Logits',
    color: '#F59E0B',
    hexColor: 0xf59e0b,
    math: 'P(w_t | w_<t) = softmax(W_vocab h_t / T)',
    role: 'Vocabulary Probability',
    details: 'Projects the final hidden states into vocabulary dimensions, passing through a temperature-controlled softmax to yield token probability distributions.',
    tensorShape: '[B, 512, 30522]',
    params: '23.44M Params (Tied weights)',
    flops: '5.01 GFLOPs',
    pytorchCode: 'logits = self.lm_head(h_t)\nprobs = F.softmax(logits / temperature, dim=-1)',
    plainEnglish: 'The Final Catalog Recommendation: The model takes the final contextualized 768-dim vector and computes similarity scores against all 30,522 words in its vocabulary dictionary. Softmax converts raw similarity scores into genuine percentages that sum to 100%. The library system selects the highest-scoring book title or word, or uses temperature sampling to produce fluent, natural responses.',
    toyExample: {
      inputDesc: 'Final Context Vector h_last ∈ ℝ^768 representing the sentence',
      computation: 'Unembedding: Logits = W_vocab * h_last. ["system": 11.4, "library": 9.8, "pizza": -4.2]',
      outputDesc: 'Softmax Probabilities: P("system") = 82.3%, P("library") = 16.7%, P("pizza") = 0.001%',
      insight: 'Temperature T controls diversity: T=0 is deterministic greedy selection; T=0.7 balances coherence and creative exploration.',
    },
    defenseQA: [
      {
        question: 'What is the mathematical effect of the Softmax temperature parameter T?',
        answer: 'Temperature modifies logits before exponentiation: P(w_i) = exp(z_i / T) / sum(exp(z_j / T)). As T approaches 0, the distribution converges to a one-hot argmax (pure deterministic output). As T approaches infinity, logits are divided by a large number, flattening probabilities into a uniform random distribution.',
      },
      {
        question: 'What is weight tying between the input embedding and output linear projection?',
        answer: 'Weight tying (Press & Wolf, 2017) sets W_vocab = W_embed^T. Because both matrices map between vocabulary tokens and the hidden embedding space, sharing parameters saves 20-30% of total model weights without degradation in language modeling perplexity.',
      },
    ],
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
    pytorchCode: 'x = batch_data.float()',
    plainEnglish: 'The Patron Profile Record: 784 normalized scalar numbers representing catalog metadata (borrowing frequency, department code, overdue score, reading velocity, days since active).',
    toyExample: {
      inputDesc: 'Patron Vector x = [0.85, 0.12, 0.94, -0.32, 0.05, ...]',
      computation: 'Raw features normalized to zero mean and unit variance: (x - μ) / σ',
      outputDesc: 'Normalized Input Vector a^[0] ∈ ℝ^784 ready for dense linear projection',
      insight: 'Feature standardization ensures all features contribute proportionally without large-magnitude features dominating gradient updates.',
    },
    defenseQA: [
      {
        question: 'Why must input features be normalized before passing into neural network layers?',
        answer: 'Unnormalized inputs create elongated elliptical loss surfaces where gradient descent oscillates erratically and requires tiny learning rates. Standardization keeps loss contours spherical, enabling fast and stable convergence.',
      },
    ],
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
    pytorchCode: 'a1 = F.relu(self.fc1(x))',
    plainEnglish: 'Pattern Detector: 256 artificial neurons compute weighted sums of the input features to detect early patterns (e.g. "frequent STEM researcher who borrows journals on weekends").',
    toyExample: {
      inputDesc: 'Input a^[0] ∈ ℝ^784 multiplied by Weight Matrix W^[1] (256 x 784) + Bias b^[1]',
      computation: 'Raw pre-activation z^[1]_1 = 2.45 → ReLU(2.45) = 2.45 | z^[1]_2 = -1.20 → ReLU(-1.20) = 0.00',
      outputDesc: 'Activated Hidden Vector a^[1] ∈ ℝ^256 with non-linear thresholding',
      insight: 'Negative activations are zeroed out, inducing sparsity and allowing the network to activate only for relevant feature patterns.',
    },
    defenseQA: [
      {
        question: 'What happens if a neural network uses no activation functions between linear layers?',
        answer: 'A composition of multiple linear transformations (W_2 * (W_1 * x)) is mathematically equivalent to a single linear transformation (W_combined * x). Non-linear activations like ReLU are strictly required for the network to approximate complex non-linear decision boundaries according to the Universal Approximation Theorem.',
      },
    ],
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
    pytorchCode: 'a2 = F.relu(self.fc2(a1))',
    plainEnglish: 'Deep Representations: Combines low-level pattern signals into complex abstract concepts (e.g. "patron is preparing a doctoral dissertation and needs high-tier monograph borrowing privileges").',
    toyExample: {
      inputDesc: 'Activated features a^[1] ∈ ℝ^256 passed to Layer 2',
      computation: 'Linear Projection: z^[2] = W^[2] a^[1] + b^[2] → Non-linear ReLU activation',
      outputDesc: 'Latent Representation a^[2] ∈ ℝ^128 (Compressed high-level semantic vector)',
      insight: 'Higher layers learn combinations of lower layer features, enabling abstract hierarchical decision rules.',
    },
    defenseQA: [
      {
        question: 'Why use deep narrow networks instead of a single very wide shallow layer?',
        answer: 'Deep networks build compositional hierarchical representations where higher layers reuse lower-level features. Eldan & Shamir (2016) proved that certain simple functions require an exponentially large number of neurons to compute with 1 hidden layer, but only polynomial neurons with 2 or more layers.',
      },
    ],
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
    pytorchCode: 'y_hat = F.softmax(self.fc3(a2), dim=-1)',
    plainEnglish: 'Decision Categorizer: 10 output neurons representing prediction targets (e.g. recommended book genres or risk of overdue return).',
    toyExample: {
      inputDesc: 'Latent vector a^[2] ∈ ℝ^128 projected to 10 class logits',
      computation: 'Logits = [3.2, 0.8, -1.5, 0.2, -0.9, 1.1, -2.0, 0.4, -0.3, 0.1] → Softmax',
      outputDesc: 'Class Probabilities: Class 0 = 82.1%, Class 5 = 10.2%, Others < 8%',
      insight: 'Probabilities sum strictly to 1.0, enabling calibrated multi-class decision boundaries.',
    },
    defenseQA: [
      {
        question: 'Why do we use Cross-Entropy Loss with Softmax instead of Mean Squared Error (MSE)?',
        answer: 'When combined with Softmax, MSE leads to non-convex optimization and severe gradient saturation when predictions are confident but wrong. Cross-Entropy cancels out the exponential in Softmax, yielding a clean gradient directly proportional to prediction error: dL/dz_i = y_hat_i - y_i.',
      },
    ],
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
    pytorchCode: 'x = self.conv1(images)  # 224x224x3 -> 112x112x64',
    plainEnglish: 'Visual Feature Sensor: Slides 64 separate 7x7 mathematical magnifying glasses across a 224x224 scanned book cover or document image, extracting edge lines, textures, and color gradients while downsampling resolution by 50%.',
    toyExample: {
      inputDesc: 'Input image: [B, 3, 224, 224] RGB scanner pixel grid',
      computation: 'Conv2d with 7x7 kernel, stride=2, padding=3: Output size = floor((224 - 7 + 2*3)/2 + 1) = 112',
      outputDesc: 'Feature maps: [B, 64, 112, 112] containing edge and corner activations',
      insight: 'Initial stride-2 downsampling cuts spatial tensor memory by 75% immediately while capturing broad visual shapes.',
    },
    defenseQA: [
      {
        question: 'Why use a large 7x7 stride-2 convolution at the input stage of ResNet?',
        answer: 'Downsampling from 224x224 to 112x112 immediately reduces the spatial memory footprint by 75% while providing a large receptive field that captures broad structural shapes before fine-grained 3x3 filters process the image.',
      },
    ],
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
    pytorchCode: 'x = self.maxpool(F.relu(self.bn1(x)))',
    plainEnglish: 'Contrast Equalizer & Feature Consolidator: Batch Normalization standardizes brightness variations across different scanner cameras, while MaxPool picks only the strongest feature signals in each 3x3 neighborhood.',
    toyExample: {
      inputDesc: 'Raw conv features: [B, 64, 112, 112]',
      computation: 'Batch normalize mini-batch, ReLU activation, 3x3 MaxPool with stride 2',
      outputDesc: 'Normalized spatial maps: [B, 64, 56, 56]',
      insight: 'Invariance to small pixel shifts and stable internal distribution across mini-batches.',
    },
    defenseQA: [
      {
        question: 'What problem does Batch Normalization solve during deep CNN training?',
        answer: 'It stabilizes internal covariate shift: as previous layers update their weights, the distribution of their outputs changes continuously. Normalizing mini-batches allows higher learning rates and acts as a mild regularizer.',
      },
    ],
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
    pytorchCode: 'identity = x\nout = self.conv1(x)  # 1x1 reduce\nout = self.conv2(out) # 3x3 spatial\nout = self.conv3(out) # 1x1 restore\nout = F.relu(out + identity)',
    plainEnglish: 'The Identity Bypass Block: A 1x1 filter compresses 256 channels down to 64 to save compute, a 3x3 filter processes spatial relationships, and another 1x1 filter restores 256 channels. Crucially, the original input features bypass the filters entirely and are added to the output (x + F(x)).',
    toyExample: {
      inputDesc: 'Input tensor x: [B, 256, 56, 56]',
      computation: '1x1 conv reduces channels 256 → 64; 3x3 conv processes spatial patterns; 1x1 conv expands 64 → 256. Identity sum: x + F(x)',
      outputDesc: 'Output tensor: [B, 256, 56, 56] with preserved identity signals',
      insight: 'The 1x1 bottleneck saves over 80% computational FLOPs compared to direct 3x3 convolutions on 256 channels!',
    },
    defenseQA: [
      {
        question: 'Why does the bottleneck design use 1x1 convolutions before and after the 3x3 convolution?',
        answer: 'Directly performing 3x3 convolutions on 256 channels requires ~590K operations per pixel. The 1x1 compression reduces channels to 64 (~16K ops), followed by 3x3 on 64 channels (~37K ops), and 1x1 restoration (~16K ops), saving over 80% FLOPs with no loss in representational capacity.',
      },
    ],
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
    pytorchCode: 'x = self.avgpool(x)  # [B, 2048, 7, 7] -> [B, 2048, 1, 1]\nx = torch.flatten(x, 1)',
    plainEnglish: 'Spatial Summarizer: Averages each of the 2,048 feature maps into a single average number, creating a compact 2,048-dimensional fingerprint of the whole image regardless of translation or positioning.',
    toyExample: {
      inputDesc: 'Deep visual feature maps: [B, 2048, 7, 7]',
      computation: 'Sum all 49 spatial activations per channel and divide by 49: mean_{h,w}(x)',
      outputDesc: 'Compact visual feature vector: [B, 2048]',
      insight: 'Zero trainable parameters and complete translation invariance.',
    },
    defenseQA: [
      {
        question: 'Why did modern CNNs replace dense fully-connected layers with Global Average Pooling?',
        answer: 'In classical VGG networks, fully connected layers accounted for 90% of all parameters (100M+ weights) and caused extreme overfitting. GAP has 0 parameters, is naturally invariant to spatial translations, and enforces direct correspondence between feature maps and categories.',
      },
    ],
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
    pytorchCode: 'logits = self.fc(x)\nprobs = F.softmax(logits, dim=-1)',
    plainEnglish: 'The Document Classifier: Multiplies the 2,048-dim visual summary by a matrix to calculate probabilities across 1,000 document/book categories.',
    toyExample: {
      inputDesc: 'Pooled vector: [B, 2048]',
      computation: 'Logits = W_{fc} * x + b. Highest activations: ["Hardcover Book": 14.2, "Notebook": 11.1, "Coffee Mug": 2.4]',
      outputDesc: 'Predicted Class: "Hardcover Book" with 94.6% confidence',
      insight: 'Enables high-accuracy visual recognition for library book drop automation and OCR document preprocessing.',
    },
    defenseQA: [
      {
        question: 'How does ResNet-50 achieve sub-3.5% top-5 error on ImageNet?',
        answer: 'The identity shortcut connections eliminate the degradation problem (where deeper networks exhibit higher training error), enabling optimization of 50 to 152 layers with smooth gradient propagation throughout the entire depth.',
      },
    ],
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
    ctx.fillStyle = 'rgba(6, 10, 23, 0.92)';
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.roundRect(10, 10, 492, 120, 24);
    ctx.fill();
    ctx.stroke();

    ctx.font = 'bold 32px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.fillText(primary, 256, 60);

    ctx.font = '500 20px -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif';
    ctx.fillStyle = '#94A3B8';
    ctx.fillText(secondary, 256, 100);
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
            {modelType === 'transformer_architecture' ? '110.1M (BERT / GPT Small)' : modelType === 'resnet50' ? '25.6M (ResNet-50)' : '235.0K (3-Layer MLP)'}
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
    // Head 1: Syntactic Dependencies
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
    // Head 2: Semantic Coreference
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
    // Head 3: Positional Locality
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
    // Head 4: Global Sequence Context
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

  // Step-by-Step Forward Pass Playback State
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);

  // Inspector Active Tab: analogy | toy_example | defense_qa | math_specs
  const [activeInspectorTab, setActiveInspectorTab] = useState<'analogy' | 'toy_example' | 'defense_qa' | 'math_specs'>('analogy');

  const selectedLayer = activeStages[currentStepIndex] || activeStages[0];
  const [activeNodeInfo, setActiveNodeInfo] = useState<string | null>(null);
  const [isRotating, setIsRotating] = useState<boolean>(true);
  const [activeCameraPreset, setActiveCameraPreset] = useState<'perspective' | 'front' | 'isometric'>('perspective');

  const firePulseRef = useRef<(() => void) | null>(null);
  const setCameraAngleRef = useRef<((mode: 'perspective' | 'front' | 'isometric') => void) | null>(null);
  const highlightStepRef = useRef<((idx: number) => void) | null>(null);

  // Reset step when activeModel changes
  useEffect(() => {
    setCurrentStepIndex(0);
    setIsPlaying(false);
  }, [activeModel]);

  // Auto-play timer effect
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setCurrentStepIndex((prev) => {
        const next = (prev + 1) % activeStages.length;
        highlightStepRef.current?.(next);
        return next;
      });
    }, 2800);
    return () => clearInterval(interval);
  }, [isPlaying, activeStages.length]);

  const handleSelectStep = useCallback((idx: number) => {
    setCurrentStepIndex(idx);
    highlightStepRef.current?.(idx);
    firePulseRef.current?.();
  }, []);

  const handleNextStep = useCallback(() => {
    setCurrentStepIndex((prev) => {
      const next = (prev + 1) % activeStages.length;
      highlightStepRef.current?.(next);
      firePulseRef.current?.();
      return next;
    });
  }, [activeStages.length]);

  const handlePrevStep = useCallback(() => {
    setCurrentStepIndex((prev) => {
      const next = prev === 0 ? activeStages.length - 1 : prev - 1;
      highlightStepRef.current?.(next);
      firePulseRef.current?.();
      return next;
    });
  }, [activeStages.length]);

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
    scene.add(new THREE.AmbientLight(0xffffff, 1.2));
    const cyanLight = new THREE.PointLight(0x38bdf8, 3.0, 90);
    cyanLight.position.set(16, 16, 16);
    scene.add(cyanLight);
    const purpleLight = new THREE.PointLight(0xa855f7, 2.5, 90);
    purpleLight.position.set(-16, -16, -16);
    scene.add(purpleLight);

    // Holographic Grid Floor
    const grid = new THREE.GridHelper(36, 36, 0x38bdf8, 0x1e293b);
    grid.position.y = -4.0;
    scene.add(grid);

    // Starfield
    const starCount = 240;
    const starGeo = new THREE.BufferGeometry();
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 70;
      starPositions[i + 1] = (Math.random() - 0.5) * 50;
      starPositions[i + 2] = (Math.random() - 0.5) * 45 - 12;
    }
    starGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    scene.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: 0x38bdf8, size: 0.18, transparent: true, opacity: 0.45 })));

    const mainGroup = new THREE.Group();
    scene.add(mainGroup);
    const interactiveObjects: THREE.Object3D[] = [];

    // Stage X Coordinates map for halo ring positioning
    let stageXCoords: number[] = [];

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
    const pulseGeo = new THREE.SphereGeometry(0.14, 12, 12);
    const pulseMat = new THREE.MeshBasicMaterial({ color: 0xffffff });

    // ── A. TRANSFORMER ARCHITECTURE ─────────────────────────────────────────
    if (isTransformer) {
      stageXCoords = [-7.0, -3.2, 0.5, 4.0, 8.5];

      // Holographic Pedestals under each stage
      stageXCoords.forEach((sx, idx) => {
        const pedGeo = new THREE.BoxGeometry(2.6, 0.25, 3.4);
        const pedMat = new THREE.MeshPhongMaterial({
          color: 0x0f172a,
          emissive: TRANSFORMER_STAGES[idx].hexColor,
          emissiveIntensity: 0.25,
          transparent: true,
          opacity: 0.75,
        });
        const pedMesh = new THREE.Mesh(pedGeo, pedMat);
        pedMesh.position.set(sx, -3.85, 0);
        mainGroup.add(pedMesh);

        const edgeGeo = new THREE.EdgesGeometry(pedGeo);
        const edgeLine = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: TRANSFORMER_STAGES[idx].hexColor, transparent: true, opacity: 0.6 }));
        edgeLine.position.copy(pedMesh.position);
        mainGroup.add(edgeLine);
      });

      const inputX = stageXCoords[0];
      const inputSprite = createTextSprite('INPUT EMBEDDINGS', 'Tokens + Positional Encoding (E+P)', '#10B981');
      inputSprite.position.set(inputX, 4.4, 0);
      mainGroup.add(inputSprite);

      const tokenNames = ['Token "Students"', 'Token "Read"', 'Token "Books"'];
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
        mesh.userData = { label: `${name} (768-dim Embedding Vector)`, meta: TRANSFORMER_STAGES[0], stepIdx: 0 };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // Attention Module (x = -3.2)
      const mhaX = stageXCoords[1];
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
        mesh.userData = { label: `${qkv.label} Matrix`, meta: TRANSFORMER_STAGES[1], stepIdx: 1 };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // 4 Parallel Attention Heads
      const headZCoords = [-1.8, -0.6, 0.6, 1.8];
      headZCoords.forEach((z, hIdx) => {
        const hPos = new THREE.Vector3(mhaX + 1.2, 0, z);
        const hMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.38, 0.38, 1.4, 16), new THREE.MeshPhongMaterial({ color: 0x8b5cf6, emissive: 0x6d28d9, emissiveIntensity: 0.5, transparent: true, opacity: 0.9 }));
        hMesh.position.copy(hPos);
        hMesh.userData = { label: `Attention Head ${hIdx + 1}/8 (d_k = 64)`, meta: TRANSFORMER_STAGES[1], stepIdx: 1 };
        mainGroup.add(hMesh);
        interactiveObjects.push(hMesh);

        qkvPositions.forEach((qPos) => {
          const lGeo = new THREE.BufferGeometry().setFromPoints([qPos, hPos]);
          mainGroup.add(new THREE.Line(lGeo, new THREE.LineBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0.35 })));
        });
      });

      // Add & LayerNorm Slab 1 (x = 0.5)
      const norm1X = stageXCoords[2];
      const norm1Sprite = createTextSprite('ADD & LAYERNORM', 'Residual Skip 1: x + Attn(x)', '#38BDF8');
      norm1Sprite.position.set(norm1X, 4.4, 0);
      mainGroup.add(norm1Sprite);

      const norm1Mesh = new THREE.Mesh(new THREE.BoxGeometry(0.6, 4.4, 2.4), new THREE.MeshPhongMaterial({ color: 0x38bdf8, emissive: 0x0284c7, emissiveIntensity: 0.35, transparent: true, opacity: 0.85 }));
      norm1Mesh.position.set(norm1X, 0, 0);
      norm1Mesh.userData = { label: 'Add & LayerNorm 1: LayerNorm(x + Attention(x))', meta: TRANSFORMER_STAGES[2], stepIdx: 2 };
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
      const ffnX = stageXCoords[3];
      const ffnSprite = createTextSprite('FEED-FORWARD NETWORK', 'Position-Wise FFN (d_ff = 3072)', '#EC4899');
      ffnSprite.position.set(ffnX, 4.4, 0);
      mainGroup.add(ffnSprite);

      const ffnY = [1.8, 0.6, -0.6, -1.8];
      ffnY.forEach((y, i) => {
        const pos = new THREE.Vector3(ffnX, y, 0);
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 0.7), new THREE.MeshPhongMaterial({ color: 0xec4899, emissive: 0xdb2777, emissiveIntensity: 0.4 }));
        mesh.position.copy(pos);
        mesh.userData = { label: `FFN Dense Unit ${i + 1} (GELU Non-Linearity)`, meta: TRANSFORMER_STAGES[3], stepIdx: 3 };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      // Output Softmax Logits (x = 8.5)
      const outX = stageXCoords[4];
      const outSprite = createTextSprite('SOFTMAX LOGITS', 'P(w_t | w_<t) Vocabulary Distribution', '#F59E0B');
      outSprite.position.set(outX, 4.4, 0);
      mainGroup.add(outSprite);

      const probHeights = [2.2, 1.4, 0.7];
      const probLabels = ['Logit: "system" (P=0.82)', 'Logit: "books" (P=0.17)', 'Logit: "coffee" (P=0.01)'];
      probHeights.forEach((h, i) => {
        const y = (i - 1) * 2.0;
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.6, h, 0.6), new THREE.MeshPhongMaterial({ color: 0xf59e0b, emissive: 0xd97706, emissiveIntensity: 0.5 }));
        mesh.position.set(outX, y, 0);
        mesh.userData = { label: probLabels[i], meta: TRANSFORMER_STAGES[4], stepIdx: 4 };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);
      });

      firePulseRef.current = () => {
        pulsePackets.forEach((p) => { p.progress = 0; p.speed = 0.024; });
      };
    }

    // ── B. RESNET-50 ARCHITECTURE ───────────────────────────────────────────
    else if (isResNet) {
      stageXCoords = [-6.0, -3.0, 0.5, 4.0, 7.5];

      // Holographic Pedestals
      stageXCoords.forEach((sx, idx) => {
        const pedGeo = new THREE.BoxGeometry(2.4, 0.25, 3.2);
        const pedMat = new THREE.MeshPhongMaterial({
          color: 0x0f172a,
          emissive: RESNET_STAGES[idx].hexColor,
          emissiveIntensity: 0.25,
          transparent: true,
          opacity: 0.75,
        });
        const pedMesh = new THREE.Mesh(pedGeo, pedMat);
        pedMesh.position.set(sx, -3.85, 0);
        mainGroup.add(pedMesh);

        const edgeGeo = new THREE.EdgesGeometry(pedGeo);
        const edgeLine = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: RESNET_STAGES[idx].hexColor, transparent: true, opacity: 0.6 }));
        edgeLine.position.copy(pedMesh.position);
        mainGroup.add(edgeLine);
      });

      const slabSizes = [
        { w: 0.5, h: 4.8, d: 4.8, c: 0x10b981, label: 'Conv1 (224x224x3 -> 112x112x64)' },
        { w: 0.5, h: 3.8, d: 3.8, c: 0x38bdf8, label: 'BatchNorm & MaxPool (56x56x64)' },
        { w: 0.6, h: 3.0, d: 3.0, c: 0x8b5cf6, label: 'Residual Bottleneck Block (56x56x256)' },
        { w: 0.6, h: 1.5, d: 1.5, c: 0xec4899, label: 'Global Average Pool (1x1x2048)' },
        { w: 0.6, h: 2.5, d: 0.8, c: 0xf59e0b, label: 'Linear 1000 Class Logits' },
      ];

      slabSizes.forEach((slab, sIdx) => {
        const x = stageXCoords[sIdx];
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(slab.w, slab.h, slab.d), new THREE.MeshPhongMaterial({ color: slab.c, emissive: slab.c, emissiveIntensity: 0.4, transparent: true, opacity: 0.85 }));
        mesh.position.set(x, 0, 0);
        mesh.userData = { label: slab.label, meta: RESNET_STAGES[sIdx], stepIdx: sIdx };
        mainGroup.add(mesh);
        interactiveObjects.push(mesh);

        const sprite = createTextSprite(RESNET_STAGES[sIdx].shortName, RESNET_STAGES[sIdx].role, RESNET_STAGES[sIdx].color);
        sprite.position.set(x, 3.8, 0);
        mainGroup.add(sprite);

        if (sIdx < slabSizes.length - 1) {
          const nextX = stageXCoords[sIdx + 1];
          const lGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(x, 0, 0), new THREE.Vector3(nextX, 0, 0)]);
          mainGroup.add(new THREE.Line(lGeo, new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.3 })));
        }
      });

      // Curved Identity Skip connection looping around bottleneck
      const curve = new THREE.CubicBezierCurve3(
        new THREE.Vector3(stageXCoords[1], 0, 1.8),
        new THREE.Vector3((stageXCoords[1] + stageXCoords[2]) / 2, 3.2, 2.5),
        new THREE.Vector3((stageXCoords[1] + stageXCoords[2]) / 2, 3.2, -2.5),
        new THREE.Vector3(stageXCoords[2], 0, 0)
      );
      mainGroup.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 32, 0.08, 8, false), new THREE.MeshPhongMaterial({ color: 0x8b5cf6, emissive: 0x6d28d9, emissiveIntensity: 0.8 })));
    }

    // ── C. MULTI-LAYER PERCEPTRON (MLP) ─────────────────────────────────────
    else {
      stageXCoords = [-5.85, -1.95, 1.95, 5.85];
      const layerCounts = [3, 4, 4, 2];
      const nodeSpacing = 2.2;
      const nodePositions: THREE.Vector3[][] = [];

      // Holographic Pedestals
      stageXCoords.forEach((sx, idx) => {
        const pedGeo = new THREE.BoxGeometry(2.4, 0.25, 3.2);
        const pedMat = new THREE.MeshPhongMaterial({
          color: 0x0f172a,
          emissive: MLP_LAYERS[idx].hexColor,
          emissiveIntensity: 0.25,
          transparent: true,
          opacity: 0.75,
        });
        const pedMesh = new THREE.Mesh(pedGeo, pedMat);
        pedMesh.position.set(sx, -3.85, 0);
        mainGroup.add(pedMesh);

        const edgeGeo = new THREE.EdgesGeometry(pedGeo);
        const edgeLine = new THREE.LineSegments(edgeGeo, new THREE.LineBasicMaterial({ color: MLP_LAYERS[idx].hexColor, transparent: true, opacity: 0.6 }));
        edgeLine.position.copy(pedMesh.position);
        mainGroup.add(edgeLine);
      });

      MLP_LAYERS.forEach((meta, lIdx) => {
        const count = layerCounts[lIdx];
        const layerNodes: THREE.Vector3[] = [];
        const x = stageXCoords[lIdx];

        const headerSprite = createTextSprite(meta.shortName, meta.role, meta.color);
        headerSprite.position.set(x, 4.4, 0);
        mainGroup.add(headerSprite);

        for (let i = 0; i < count; i++) {
          const y = (i - (count - 1) / 2) * nodeSpacing;
          const pos = new THREE.Vector3(x, y, 0);
          layerNodes.push(pos);

          const nodeMesh = new THREE.Mesh(new THREE.SphereGeometry(0.44, 24, 24), new THREE.MeshPhongMaterial({ color: meta.hexColor, emissive: meta.hexColor, emissiveIntensity: 0.45, shininess: 95 }));
          nodeMesh.position.copy(pos);
          nodeMesh.userData = { label: `${meta.title} (Neuron ${i + 1}/${count})`, meta, stepIdx: lIdx };
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

    // ── D. ACTIVE STAGE GLOWING HALO RING ────────────────────────────────────
    const haloGeo = new THREE.TorusGeometry(1.5, 0.07, 16, 64);
    const haloMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.85 });
    const haloMesh = new THREE.Mesh(haloGeo, haloMat);
    haloMesh.rotation.x = Math.PI / 2;
    haloMesh.position.set(stageXCoords[currentStepIndex] || 0, -3.7, 0);
    mainGroup.add(haloMesh);

    // Dynamic Step Highlight Function
    highlightStepRef.current = (idx: number) => {
      const targetX = stageXCoords[idx];
      if (targetX !== undefined) {
        haloMesh.position.x = targetX;
        const stageColor = activeStages[idx]?.hexColor || 0x38bdf8;
        haloMat.color.setHex(stageColor);
      }
    };

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

      // Pulse halo
      const scale = 1.0 + Math.sin(Date.now() * 0.006) * 0.06;
      haloMesh.scale.set(scale, scale, scale);

      pulsePackets.forEach((p) => {
        p.progress += p.speed;
        if (p.progress > 1) p.progress = 0;
        if (p.isCurve && p.curve) p.mesh.position.copy(p.curve.getPoint(p.progress));
      });
      renderer.render(scene, camera);
    };
    animate();

    // Raycaster & Mouse Interaction
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
        if (hit.userData?.stepIdx !== undefined) {
          handleSelectStep(hit.userData.stepIdx);
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
              <div style={{ fontSize: '0.62rem', color: '#94A3B8' }}>
                Interactive Forward Pass Scrubber · Holographic Grid · 4-Tab Educational Inspector
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
              title="Open full-screen industry evaluation studio"
            >
              <span>⛶</span> Fullscreen Studio
            </button>
          </div>
        </div>

        {/* Small Inline 3D Canvas */}
        <div style={{ position: 'relative' }}>
          <div ref={mountRef} style={{ width: '100%', height: '230px', position: 'relative', cursor: 'grab' }} />

          {/* Quick Inline Scrubber */}
          <div
            style={{
              position: 'absolute',
              bottom: '8px',
              left: '8px',
              right: '8px',
              background: 'rgba(6, 10, 23, 0.88)',
              backdropFilter: 'blur(8px)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              borderRadius: '8px',
              padding: '6px 10px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <button
                type="button"
                onClick={handlePrevStep}
                style={{ background: 'transparent', border: 'none', color: '#38BDF8', cursor: 'pointer', fontSize: '0.75rem' }}
                title="Previous Step"
              >
                ◀
              </button>
              <button
                type="button"
                onClick={() => setIsPlaying((p) => !p)}
                style={{
                  fontSize: '0.68rem',
                  padding: '2px 8px',
                  borderRadius: '4px',
                  border: '1px solid rgba(56, 189, 248, 0.4)',
                  background: isPlaying ? 'rgba(56, 189, 248, 0.3)' : 'rgba(255, 255, 255, 0.05)',
                  color: '#38BDF8',
                  cursor: 'pointer',
                  fontWeight: 700,
                }}
              >
                {isPlaying ? '⏸️ Pause' : '▶ Play'}
              </button>
              <button
                type="button"
                onClick={handleNextStep}
                style={{ background: 'transparent', border: 'none', color: '#38BDF8', cursor: 'pointer', fontSize: '0.75rem' }}
                title="Next Step"
              >
                ▶
              </button>
            </div>

            <div style={{ fontSize: '0.7rem', color: '#E2E8F0', fontWeight: 600 }}>
              Step {currentStepIndex + 1}/{activeStages.length}: <span style={{ color: selectedLayer?.color }}>{selectedLayer?.shortName}</span>
            </div>

            <button
              type="button"
              onClick={() => setIsFullscreen(true)}
              style={{ fontSize: '0.68rem', color: '#A78BFA', background: 'transparent', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
            >
              Inspect Details ➔
            </button>
          </div>
        </div>
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
                <div style={{ fontSize: '0.72rem', color: '#94A3B8' }}>
                  Interactive Forward Pass Scrubber · Holographic Grid · 4-Tab Viva Defense Inspector
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
                    ⚡ Pulse Synapses
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
                {/* Top Info Banner */}
                <div style={{ position: 'absolute', top: '16px', left: '16px', background: 'rgba(8, 13, 26, 0.88)', border: '1px solid rgba(255, 255, 255, 0.12)', borderRadius: '8px', padding: '8px 14px', color: '#94A3B8', fontSize: '0.75rem', pointerEvents: 'none', zIndex: 10 }}>
                  🖱️ Orbit: Left-Click & Drag · Zoom: Scroll · Cyan Grid Floor = Holographic Ground Plane
                </div>

                {activeNodeInfo && (
                  <div style={{ position: 'absolute', top: '16px', right: '16px', background: 'rgba(15, 23, 42, 0.96)', border: '1px solid #38BDF8', borderRadius: '8px', padding: '8px 18px', color: '#38BDF8', fontSize: '0.82rem', fontWeight: 600, zIndex: 10 }}>
                    🎯 Selected Object: {activeNodeInfo}
                  </div>
                )}

                {/* ── STEP-BY-STEP FORWARD PASS SCRUBBER BAR ──────────────────── */}
                <div
                  style={{
                    position: 'absolute',
                    bottom: '20px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    background: 'rgba(6, 10, 23, 0.94)',
                    backdropFilter: 'blur(12px)',
                    border: '1px solid rgba(56, 189, 248, 0.45)',
                    borderRadius: '14px',
                    padding: '10px 18px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    boxShadow: '0 12px 36px rgba(0, 0, 0, 0.8)',
                    zIndex: 20,
                    maxWidth: '92%',
                    overflowX: 'auto',
                  }}
                >
                  {/* Transport Playback Buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      type="button"
                      onClick={() => handleSelectStep(0)}
                      style={{ background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.12)', color: '#94A3B8', borderRadius: '6px', padding: '5px 8px', cursor: 'pointer', fontSize: '0.75rem' }}
                      title="Jump to First Stage"
                    >
                      ⏮️
                    </button>
                    <button
                      type="button"
                      onClick={handlePrevStep}
                      style={{ background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.12)', color: '#38BDF8', borderRadius: '6px', padding: '5px 10px', cursor: 'pointer', fontSize: '0.78rem' }}
                      title="Previous Stage"
                    >
                      ◀
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsPlaying((p) => !p)}
                      style={{
                        background: isPlaying ? 'rgba(56, 189, 248, 0.25)' : 'rgba(16, 185, 129, 0.2)',
                        border: `1px solid ${isPlaying ? '#38BDF8' : '#10B981'}`,
                        color: isPlaying ? '#38BDF8' : '#10B981',
                        borderRadius: '6px',
                        padding: '5px 12px',
                        cursor: 'pointer',
                        fontSize: '0.78rem',
                        fontWeight: 700,
                      }}
                      title={isPlaying ? 'Pause Auto-Play' : 'Auto-Play Forward Pass'}
                    >
                      {isPlaying ? '⏸️ Pause' : '▶ Play'}
                    </button>
                    <button
                      type="button"
                      onClick={handleNextStep}
                      style={{ background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.12)', color: '#38BDF8', borderRadius: '6px', padding: '5px 10px', cursor: 'pointer', fontSize: '0.78rem' }}
                      title="Next Stage"
                    >
                      ▶
                    </button>
                    <button
                      type="button"
                      onClick={() => handleSelectStep(activeStages.length - 1)}
                      style={{ background: 'rgba(255, 255, 255, 0.06)', border: '1px solid rgba(255, 255, 255, 0.12)', color: '#94A3B8', borderRadius: '6px', padding: '5px 8px', cursor: 'pointer', fontSize: '0.75rem' }}
                      title="Jump to Output Stage"
                    >
                      ⏭️
                    </button>
                  </div>

                  <div style={{ width: '1px', height: '24px', background: 'rgba(255, 255, 255, 0.15)' }} />

                  {/* Discrete Stage Step Pills */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {activeStages.map((stage, idx) => {
                      const isActive = currentStepIndex === idx;
                      return (
                        <button
                          key={stage.id}
                          type="button"
                          onClick={() => handleSelectStep(idx)}
                          style={{
                            padding: '5px 10px',
                            borderRadius: '6px',
                            border: `1px solid ${isActive ? stage.color : 'rgba(255, 255, 255, 0.1)'}`,
                            background: isActive ? `${stage.color}25` : 'rgba(255, 255, 255, 0.04)',
                            color: isActive ? '#FFFFFF' : '#94A3B8',
                            fontSize: '0.74rem',
                            fontWeight: isActive ? 700 : 500,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            transition: 'all 0.15s ease',
                            boxShadow: isActive ? `0 0 12px ${stage.color}40` : 'none',
                          }}
                        >
                          <span style={{ width: '16px', height: '16px', borderRadius: '50%', background: isActive ? stage.color : 'rgba(255,255,255,0.2)', color: isActive ? '#040711' : '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.65rem', fontWeight: 800 }}>
                            {idx + 1}
                          </span>
                          <span>{stage.shortName}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}

            {activeStudioMode === 'compute_dag' && (
              <ComputeDAGView
                modelType={activeModel}
                selectedLayerId={selectedLayer?.id || null}
                onSelectLayer={(l) => {
                  const idx = activeStages.findIndex((s) => s.id === l.id);
                  if (idx !== -1) handleSelectStep(idx);
                }}
              />
            )}

            {activeStudioMode === 'attention_heatmap' && (
              <AttentionHeatmapView />
            )}

            {/* ── RIGHT 4-TAB EDUCATIONAL INSPECTOR PANEL ──────────────────── */}
            <div
              style={{
                width: '420px',
                borderLeft: '1px solid rgba(56, 189, 248, 0.2)',
                background: 'rgba(10, 16, 31, 0.98)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              {/* Layer Title Header */}
              <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(15, 23, 42, 0.7)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <div style={{ width: '10px', height: '10px', borderRadius: '50%', background: selectedLayer?.color, boxShadow: `0 0 10px ${selectedLayer?.color}` }} />
                    <span style={{ fontSize: '0.7rem', fontWeight: 700, color: selectedLayer?.color, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Stage {currentStepIndex + 1}/{activeStages.length} · {selectedLayer?.role}
                    </span>
                  </div>
                  {selectedLayer?.tensorShape && (
                    <code style={{ fontSize: '0.72rem', color: '#38BDF8', background: 'rgba(56, 189, 248, 0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                      {selectedLayer.tensorShape}
                    </code>
                  )}
                </div>
                <h3 style={{ fontSize: '1.02rem', fontWeight: 700, color: '#F8FAFC', margin: 0 }}>
                  {selectedLayer?.title}
                </h3>
              </div>

              {/* 4 Inspector Navigation Tabs */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', background: 'rgba(6, 10, 23, 0.95)', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <button
                  type="button"
                  onClick={() => setActiveInspectorTab('analogy')}
                  style={{
                    padding: '0.65rem 0.35rem',
                    background: activeInspectorTab === 'analogy' ? 'rgba(56, 189, 248, 0.15)' : 'transparent',
                    border: 'none',
                    borderBottom: `2px solid ${activeInspectorTab === 'analogy' ? '#38BDF8' : 'transparent'}`,
                    color: activeInspectorTab === 'analogy' ? '#38BDF8' : '#94A3B8',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                  title="Plain-English library & real-world analogy"
                >
                  💡 Analogy
                </button>
                <button
                  type="button"
                  onClick={() => setActiveInspectorTab('toy_example')}
                  style={{
                    padding: '0.65rem 0.35rem',
                    background: activeInspectorTab === 'toy_example' ? 'rgba(139, 92, 246, 0.15)' : 'transparent',
                    border: 'none',
                    borderBottom: `2px solid ${activeInspectorTab === 'toy_example' ? '#8B5CF6' : 'transparent'}`,
                    color: activeInspectorTab === 'toy_example' ? '#A78BFA' : '#94A3B8',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                  title="Toy example with concrete numbers"
                >
                  🔢 Numbers
                </button>
                <button
                  type="button"
                  onClick={() => setActiveInspectorTab('defense_qa')}
                  style={{
                    padding: '0.65rem 0.35rem',
                    background: activeInspectorTab === 'defense_qa' ? 'rgba(16, 185, 129, 0.15)' : 'transparent',
                    border: 'none',
                    borderBottom: `2px solid ${activeInspectorTab === 'defense_qa' ? '#10B981' : 'transparent'}`,
                    color: activeInspectorTab === 'defense_qa' ? '#34D399' : '#94A3B8',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                  title="Academic evaluator viva defense Q&A"
                >
                  🎓 Viva Q&A
                </button>
                <button
                  type="button"
                  onClick={() => setActiveInspectorTab('math_specs')}
                  style={{
                    padding: '0.65rem 0.35rem',
                    background: activeInspectorTab === 'math_specs' ? 'rgba(245, 158, 11, 0.15)' : 'transparent',
                    border: 'none',
                    borderBottom: `2px solid ${activeInspectorTab === 'math_specs' ? '#F59E0B' : 'transparent'}`,
                    color: activeInspectorTab === 'math_specs' ? '#FBBF24' : '#94A3B8',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    cursor: 'pointer',
                    textAlign: 'center',
                  }}
                  title="Mathematical formulas, tensor shapes, and code"
                >
                  📐 Specs
                </button>
              </div>

              {/* Tab Content Body */}
              <div style={{ flex: 1, overflowY: 'auto', padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* ── TAB 1: PLAIN-ENGLISH ANALOGY ────────────────────────────── */}
                {activeInspectorTab === 'analogy' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ background: 'rgba(56, 189, 248, 0.08)', border: '1px solid rgba(56, 189, 248, 0.25)', borderRadius: '10px', padding: '1rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                        <span style={{ fontSize: '1.1rem' }}>🏛️</span>
                        <span style={{ fontSize: '0.78rem', fontWeight: 700, color: '#38BDF8', textTransform: 'uppercase' }}>
                          Library Metaphor Breakdown
                        </span>
                      </div>
                      <p style={{ fontSize: '0.84rem', color: '#E2E8F0', lineHeight: 1.6, margin: 0 }}>
                        {selectedLayer?.plainEnglish}
                      </p>
                    </div>

                    <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '10px', padding: '1rem' }}>
                      <div style={{ fontSize: '0.72rem', color: '#64748B', fontWeight: 700, textTransform: 'uppercase', marginBottom: '0.4rem' }}>
                        Core Purpose in the Forward Pass
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#CBD5E1', lineHeight: 1.55 }}>
                        {selectedLayer?.details}
                      </div>
                    </div>
                  </div>
                )}

                {/* ── TAB 2: TOY NUMERICAL EXAMPLE ────────────────────────────── */}
                {activeInspectorTab === 'toy_example' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
                    <div style={{ fontSize: '0.75rem', color: '#A78BFA', fontWeight: 700, textTransform: 'uppercase' }}>
                      Step-by-Step Numerical Walkthrough
                    </div>

                    {/* Input */}
                    <div style={{ background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(139, 92, 246, 0.3)', borderRadius: '8px', padding: '0.85rem' }}>
                      <div style={{ fontSize: '0.68rem', color: '#94A3B8', fontWeight: 700 }}>1. INPUT STATE</div>
                      <code style={{ display: 'block', fontSize: '0.76rem', color: '#E2E8F0', marginTop: '4px', wordBreak: 'break-word', fontFamily: 'monospace' }}>
                        {selectedLayer?.toyExample.inputDesc}
                      </code>
                    </div>

                    {/* Computation */}
                    <div style={{ background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '8px', padding: '0.85rem' }}>
                      <div style={{ fontSize: '0.68rem', color: '#38BDF8', fontWeight: 700 }}>2. MATHEMATICAL COMPUTATION</div>
                      <code style={{ display: 'block', fontSize: '0.76rem', color: '#38BDF8', marginTop: '4px', wordBreak: 'break-word', fontFamily: 'monospace' }}>
                        {selectedLayer?.toyExample.computation}
                      </code>
                    </div>

                    {/* Output */}
                    <div style={{ background: 'rgba(15, 23, 42, 0.9)', border: '1px solid rgba(16, 185, 129, 0.3)', borderRadius: '8px', padding: '0.85rem' }}>
                      <div style={{ fontSize: '0.68rem', color: '#10B981', fontWeight: 700 }}>3. RESULTING OUTPUT TENSOR</div>
                      <code style={{ display: 'block', fontSize: '0.76rem', color: '#10B981', marginTop: '4px', wordBreak: 'break-word', fontFamily: 'monospace' }}>
                        {selectedLayer?.toyExample.outputDesc}
                      </code>
                    </div>

                    {/* Key Insight */}
                    <div style={{ background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)', borderRadius: '8px', padding: '0.85rem', fontSize: '0.78rem', color: '#FCD34D', lineHeight: 1.5 }}>
                      💡 <strong style={{ color: '#F59E0B' }}>Numerical Insight:</strong> {selectedLayer?.toyExample.insight}
                    </div>
                  </div>
                )}

                {/* ── TAB 3: EXAMINER DEFENSE Q&A ──────────────────────────────── */}
                {activeInspectorTab === 'defense_qa' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
                    <div style={{ fontSize: '0.75rem', color: '#34D399', fontWeight: 700, textTransform: 'uppercase' }}>
                      Professor Viva & Evaluation Questions
                    </div>

                    {selectedLayer?.defenseQA.map((qa, qIdx) => (
                      <div
                        key={qIdx}
                        style={{
                          background: 'rgba(15, 23, 42, 0.85)',
                          border: '1px solid rgba(16, 185, 129, 0.25)',
                          borderRadius: '10px',
                          padding: '1rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.5rem',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.45rem' }}>
                          <span style={{ fontSize: '0.85rem', color: '#10B981', fontWeight: 800 }}>Q:</span>
                          <span style={{ fontSize: '0.82rem', fontWeight: 700, color: '#F1F5F9', lineHeight: 1.4 }}>
                            {qa.question}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.45rem', marginTop: '2px' }}>
                          <span style={{ fontSize: '0.85rem', color: '#38BDF8', fontWeight: 800 }}>A:</span>
                          <span style={{ fontSize: '0.78rem', color: '#CBD5E1', lineHeight: 1.55 }}>
                            {qa.answer}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* ── TAB 4: MATH & TENSOR SPECS ──────────────────────────────── */}
                {activeInspectorTab === 'math_specs' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {/* Math Formulation */}
                    <div style={{ background: 'rgba(6, 10, 23, 0.95)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                      <div style={{ fontSize: '0.65rem', color: '#64748B', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 700 }}>
                        Mathematical Formulation
                      </div>
                      <code style={{ fontSize: '0.82rem', color: '#38BDF8', wordBreak: 'break-all', fontWeight: 600 }}>
                        {selectedLayer?.math}
                      </code>
                    </div>

                    {/* Telemetry Grid */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px', padding: '0.6rem 0.8rem' }}>
                        <div style={{ fontSize: '0.65rem', color: '#64748B' }}>TENSOR SHAPE</div>
                        <div style={{ fontSize: '0.8rem', color: '#38BDF8', fontWeight: 700 }}>{selectedLayer?.tensorShape || 'N/A'}</div>
                      </div>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px', padding: '0.6rem 0.8rem' }}>
                        <div style={{ fontSize: '0.65rem', color: '#64748B' }}>PARAM COUNT</div>
                        <div style={{ fontSize: '0.8rem', color: '#F59E0B', fontWeight: 700 }}>{selectedLayer?.params?.split('(')[0] || '0'}</div>
                      </div>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px', padding: '0.6rem 0.8rem' }}>
                        <div style={{ fontSize: '0.65rem', color: '#64748B' }}>COMPUTE FLOPS</div>
                        <div style={{ fontSize: '0.8rem', color: '#10B981', fontWeight: 700 }}>{selectedLayer?.flops || 'N/A'}</div>
                      </div>
                      <div style={{ background: 'rgba(15, 23, 42, 0.8)', border: '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '6px', padding: '0.6rem 0.8rem' }}>
                        <div style={{ fontSize: '0.65rem', color: '#64748B' }}>PRECISION</div>
                        <div style={{ fontSize: '0.8rem', color: '#A78BFA', fontWeight: 700 }}>BFloat16</div>
                      </div>
                    </div>

                    {/* PyTorch Reference Snippet */}
                    {selectedLayer?.pytorchCode && (
                      <div style={{ background: 'rgba(6, 10, 23, 0.95)', padding: '0.75rem 1rem', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                        <div style={{ fontSize: '0.65rem', color: '#64748B', marginBottom: '4px', textTransform: 'uppercase', fontWeight: 700 }}>
                          PyTorch 2.4 Reference Implementation
                        </div>
                        <pre style={{ margin: 0, fontSize: '0.72rem', color: '#E2E8F0', fontFamily: 'monospace', whiteSpace: 'pre-wrap', lineHeight: 1.45 }}>
                          {selectedLayer.pytorchCode}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Bottom Viva Quick Tip Banner */}
              <div style={{ padding: '0.85rem 1.25rem', borderTop: '1px solid rgba(255, 255, 255, 0.08)', background: 'rgba(6, 10, 23, 0.95)', fontSize: '0.74rem', color: '#94A3B8', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                  <span>🎯</span>
                  <span>Use <strong>[◀] [▶]</strong> to scrub forward pass</span>
                </div>
                <button
                  type="button"
                  onClick={handleNextStep}
                  style={{
                    background: 'rgba(56, 189, 248, 0.15)',
                    border: '1px solid rgba(56, 189, 248, 0.4)',
                    color: '#38BDF8',
                    padding: '3px 8px',
                    borderRadius: '4px',
                    fontSize: '0.72rem',
                    cursor: 'pointer',
                    fontWeight: 600,
                  }}
                >
                  Next Stage ➔
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
