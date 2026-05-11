# 杨立昆（Yann LeCun）vs AI主流：一场关于大模型路线的深层分歧

> 验证日期：2026年4月24日  
> 信息来源：LeCun公开演讲、Lex Fridman专访（2024年3月）、Financial Times专访（2025年）、论文《A Path Towards Autonomous Machine Intelligence》（2022年OpenReview）、诺贝尔奖采访（Hinton, 2024年12月）、DeepMind博客（Genie, 2024年12月）、Sutskever专访（Dwarkesh Patel, 2025年11月）

---

## 一、杨立昆是谁？以及他为什么要"唱反调"

杨立昆（Yann LeCun）是深度学习三巨头之一、2018年图灵奖得主。**他已于2025年11月离开Meta首席AI科学家职位，创立AMI Labs。** 在Meta期间，他长期主导FAIR（基础AI研究）实验室，该实验室明确不直接参与LLM产品竞赛，而是专注于更基础的AI架构研究。

他的"唱反调"并非出于对抗，而是基于一个根本判断：**当前主流的自回归大语言模型（Autoregressive LLM），无论怎么扩大规模，都存在先天性的架构缺陷，无法通向通用人工智能（AGI）。**

这个判断不是随口说的。他在2022年就系统性地发表了完整的技术蓝图《A Path Towards Autonomous Machine Intelligence》，提出了替代路径。而在2024-2025年的多次公开访谈中，他用更直白的方式解释了为什么LLM不行。

---

## 二、他对LLM的四层核心批判（基于原话整理）

### 第一层："死胡同"判断

LeCun的原话是：

> "I'm sure there's a lot of people at Meta who would like me to NOT tell the world that LLMs basically are a dead end when it comes to superintelligence."
> — Financial Times专访，2025年

NYT在2026年1月的标题直接引用了他的判断："An A.I. Pioneer Warns the Tech Herd Is Marching Into a Dead End."

**注意**：他说的"dead end"是指**通向超级智能/AGI的路径**，而不是说LLM作为技术本身没有价值。他承认LLM在文本处理、编程辅助等任务上有用，但认为它不具备继续"进化"成通用智能的潜力。

### 第二层："不如一只猫"

LeCun在多个场合做过这个比较：

> "Current artificial intelligence systems like ChatGPT... are not even as smart as a dog."
> — CNBC，2023年6月

> "Even the most advanced A.I. systems today have less common sense than a house cat... A cat can remember, can understand the physical world, can plan complex actions, can do some level of reasoning—actually much better than the biggest LLMs."
> — Observer，2024年2月

这个比较的核心逻辑是：LLM从未通过感官与现实世界交互过。猫在成长过程中通过视觉、触觉、运动不断积累物理直觉（物体恒存、重力、因果关系），而LLM只见过文本——文本是人类经验的"蒸馏"，不是经验本身。所以LLM可以流畅地谈论"杯子会摔碎"，但它并不**理解**杯子摔碎意味着什么。

### 第三层：幻觉是"先天缺陷"，不是bug

LeCun对幻觉的分析不是情绪化的批评，而是数学性的：

> "Because of the autoregressive prediction, every time [it] produces a token or a word, there is some level of probability for that word to take you out of the set of reasonable answers... every time you produce a token, the probability that you stay within the set of correct answers decreases and it decreases exponentially."
> — Lex Fridman Podcast，2024年3月

他的意思是：自回归模型每生成一个token，就有概率"跑偏"；随着生成序列变长，"保持在正确轨道上"的概率呈指数级衰减。这不是可以通过更多数据或更大模型"修好的bug"，而是这种架构在数学上的固有限制。Fine-tuning只能在常见场景上掩盖问题，但面对海量长尾场景时，模型必然失控。

### 第四层：对"军备竞赛"的隐性批评

LeCun没有公开说过"LLM军备竞赛吸走了所有资源"这种话（未找到直接出处）。但他的行动说明了立场：他在Meta期间坚持让FAIR做基础研究，不直接参与产品化的LLM竞赛；2025年离开Meta创立独立实验室，也是为了摆脱商业压力、追求长期研究。媒体（如36kr）报道称他"没有选择加入大语言模型的军备竞赛"。

---

## 三、他的替代方案：世界模型 + JEPA

### 3.1 什么是世界模型？

世界模型（World Model）的核心思想很简单：**让AI像人类一样，在脑子里"模拟"世界。**

人类做决策时，不需要真的去试错。你想把杯子放到桌上，大脑会先在内部模拟"如果我松手，杯子会下落、停在桌面上、不会摔碎"，然后才执行动作。这种"内部模拟"的能力——预测动作的后果、理解因果关系、进行长期规划——就是世界模型要赋予AI的能力。

### 3.2 LeCun的技术蓝图：四输入预测系统

在演讲和技术论文中，LeCun将世界模型定义为一个序列预测系统，核心输入包括四个变量：

| 变量 | 含义 |
|------|------|
| **x(t)** | 当前对世界的观测（如摄像头画面） |
| **s(t)** | 对世界当前状态的内部估计（抽象表征） |
| **a(t)** | 拟执行的动作 |
| **z(t)** | 代表世界不确定性的潜在变量 |

系统逻辑：编码器将原始观测x(t)转化为抽象状态s(t)，然后预测器结合s(t)、a(t)、z(t)，预测下一时刻的世界状态s(t+1)。

**关键点**：预测的是**抽象状态**，不是像素、不是文字。机器只需要知道"杯子的位置从A变到了B"，不需要生成一张逼真的杯子图片。这使得系统可以忽略无关细节，专注于因果和规划。

### 3.3 JEPA：放弃"生成"，专注"预测表征"

JEPA全称Joint-Embedding Predictive Architecture（联合嵌入预测架构），是LeCun提出的一套自监督学习框架。

传统生成式模型（如扩散模型、GPT）需要在像素空间或token空间重建输入，JEPA则完全不同：

- **输入**：一张图片或一段视频
- **操作**：遮住部分区域
- **目标**：不是重建被遮住的像素，而是预测被遮住区域在**抽象表征空间**中的嵌入向量
- **结果**：学习到的表征包含语义信息（"这是杯子的边缘"），而不是低级的像素值

LeCun的原话：

> "If you're really interested in human level AI, abandon the idea of generative AI."
> — Lex Fridman Podcast，2024年3月

他认为生成式路径（预测像素/token）引入了海量冗余信息，效率低下，而且"能生成"不等于"能理解"。JEPA走"表征预测"路线，只为决策和规划服务。

### 3.4 一个需要修正的原版错误

原内容说："当前的自回归LLM只是世界模型的一个极度简化的特例"。**这是不准确的。**

LeCun的原意是两层：
1. **LLM是自监督学习的一个特例**（special case of self-supervised learning）——这他确实说过；
2. **但LLM不是世界模型**——他也明确说过："Can you build it by predicting words? And the answer is most probably no... building world models means observing the world."

所以LLM和世界模型是**两条不同的路线**，不是"简化版"和"完整版"的关系。LLM完全缺失了动作变量a(t)、物理世界观测x(t)和状态估计s(t)这些世界模型的核心组件。

---

## 四、他与AI大佬们的真实分歧

### 4.1 与杰弗里·辛顿（Geoffrey Hinton）：40年老友，理念渐行渐远

**关系基础**：LeCun于1987年到多伦多大学做Hinton的博士后，两人合作发明了反向传播在神经网络中的应用。到2025年，这段专业关系和友谊已经持续了约38-39年。称"40年"是合理的近似。

**分歧焦点：LLM到底有没有"理解"？**

| 维度 | 杨立昆 | 辛顿 |
|------|--------|------|
| **LLM的理解能力** | LLM只是在操纵语言的统计规律，没有真正的理解 | "Some scientists say... they don't really understand what they're saying despite all the evidence that they do understand what they're saying."（诺贝尔奖采访，2024年12月） |
| **通向AGI的路径** | 自回归LLM是死胡同，需要世界模型和物理交互 | 承认LLM有局限，但相信通过架构改进和规模扩张，大模型可以持续进化，最终实现超越人类的智能 |
| **AI安全风险** | "AI威胁论是胡说八道"，当前AI远不及人类，过度渲染风险会阻碍技术发展 | 晚年公开转变立场，警告超级AI可能在5-20年内出现（50%概率），呼吁加强监管和安全对齐 |
| **智能的核心来源** | 智能根基是对物理世界的感知、建模与交互，语言只是副产品 | 语言是智能的核心载体，大模型通过文本学习到的逻辑足以支撑高级智能 |

**一句话总结**：Hinton认为LLM已经展现出某种"理解"，且持续scaling+改进可以通向AGI，同时他对AI风险高度警惕；LeCun认为LLM根本没有理解，必须彻底换路线，且当前AI风险被夸大。

### 4.2 与伊利亚·萨茨克韦弗（Ilya Sutskever）：技术路线的直接对抗，但对手也在变

**历史立场**：Sutskever作为OpenAI联合创始人兼前首席科学家，是LLM scaling路线的核心推动者。他曾坚信：
- 自回归语言模型是AGI的正确路径
- 通过扩大规模+优化数据+RLHF对齐，大模型会持续涌现更强能力
- 幻觉问题最终可以解决

**2025年的转变**：在Dwarkesh Patel的专访（2025年11月）中，Sutskever宣布：

> "The Age of Scaling is over. We are now entering the Age of Research."

他明确表示预训练（pre-training）的scaling已经遇到瓶颈，需要全新的研究思路来提升泛化能力。**这意味着他与LeCun的分歧正在缩小**——两人都开始认为"单纯scaling自回归LLM不够"，只是LeCun更早、更彻底地否定这条路线，而Sutskever是在推动这条路线到极限之后才承认需要新方向。

**仍然存在的分歧**：
- **开源vs闭源**：LeCun是开源的坚定捍卫者，批评OpenAI"不是真正的研究"；OpenAI长期闭源，认为闭源是安全的必要手段。
- **研究范式**：LeCun坚持学术论文和可复现实验；OpenAI以产品化发布为主，极少公开核心技术细节。

### 4.3 与德米斯·哈萨比斯（Demis Hassabis）/DeepMind：世界模型的"生成派"vs"表征派"

**共识**：两人都认为当前LLM缺乏对物理世界的理解，必须构建世界模型才能实现真正的智能。

**分歧**：世界模型该怎么建？

| 路线 | DeepMind（哈萨比斯） | 杨立昆 |
|------|---------------------|--------|
| **方法** | 生成式世界模型：预测像素/视频帧 | 表征式世界模型：预测抽象状态（JEPA） |
| **代表成果** | Genie 2（2024年12月）：基于大规模视频训练，生成可交互的虚拟世界 | V-JEPA、I-JEPA、C-JEPA系列：在潜在空间预测表征，不生成像素 |
| **核心逻辑** | "能创造即能理解"——能精准生成世界动态，说明理解了世界 | "能预测抽象状态、完成规划即能理解"——生成不是理解的必要条件 |
| **对LLM的态度** | 可以在Transformer和自回归基础上"打补丁"，通过混合模型、搜索规划等方式改良 | 自回归范式必须被彻底抛弃，没有改良空间 |

**注意**："生成派vs表征派"这个标签是分析者的总结框架，不是Hassabis或LeCun的直接表述。但两人的研究路线确实清晰地分化为这两个方向。

### 4.4 其他分歧对象简述

- **埃隆·马斯克/xAI**：分歧主要在开源理念和AI风险认知上。马斯克也批评OpenAI闭源，但同时对AI安全高度警惕，与LeCun的"风险被夸大"立场不完全一致。
- **Noam Brown（OpenAI o1核心开发者）**：o1通过"测试时计算"（test-time compute）和搜索来增强推理能力，这某种程度上是对LeCun"LLM无法规划"批评的一种回应，但LeCun可能会认为这仍然是"在自回归范式上打补丁"。

---

## 五、分歧最大的对象：取决于你怎么定义"分歧"

原内容说"分歧最大的对象是辛顿"，这个说法有一定道理，但需要分维度看：

| 维度 | 最大分歧对象 | 原因 |
|------|-------------|------|
| **理念对立的彻底性** | 辛顿 | 两人在"AI是否危险""LLM是否有理解"这两个根本问题上完全对立，且有近40年的交情，使得分歧更具戏剧性和公众关注度 |
| **技术路线的直接对抗** | 萨茨克韦弗/OpenAI | 一方是LLM scaling路线的旗手，一方是该路线最坚定的批判者，交锋最具体、最频繁 |
| **世界模型实现路径的分歧** | 哈萨比斯 | 两人都在研究世界模型，但方法完全不同，且各自代表了产业界两大顶级AI实验室的路线 |

**修正后的判断**：如果只能选一个"分歧最大"，辛顿是合理的答案——因为两人的分歧覆盖"技术+安全+哲学"三个层面，且Hinton的"AI威胁论"与LeCun的"完全否定威胁论"形成最鲜明的对比。但Sutskever作为技术路线的直接对立者，同样值得并列强调。

---

## 六、2025-2026年的最新变化

这场分歧不是静态的。几个关键变化：

1. **LeCun离开Meta**（2025年11月）：摆脱大公司约束后，他的批评可能更直接，世界模型研究也可能更聚焦。

2. **Sutskever承认scaling结束**（2025年11月）：LLM scaling路线的核心推动者之一"倒戈"，意味着行业共识正在从"scale就是一切"转向"需要新架构"。

3. **LeCun开始融合LLM和JEPA**（2025年9月论文LLM-JEPA）：他并非完全排斥LLM技术本身，而是在探索如何将JEPA的自监督表征学习优势引入语言模型训练。这说明他的立场是"LLM需要根本性改造"，而非"LLM一文不值"。

4. **Genie 2的发布**（2024年12月）：DeepMind的生成式世界模型取得了实质性进展，让"生成派vs表征派"的争论有了更具体的实验基础，而不是纯理论对峙。

---

## 七、总结：这场争论的本质

LeCun与AI主流的争论，本质上是**两种智能观**的冲突：

- **LLM路线**：智能可以通过语言的统计规律"涌现"出来。给足够多的文本，模型就能学会推理、规划和理解。
- **LeCun路线**：智能必须植根于物理世界。没有与世界的交互、没有因果模型、没有长期规划能力，仅靠文本预测不可能产生真正的理解。

这场争论目前还没有定论。LLM路线的产品成果（ChatGPT、Claude、o1）已经改变了世界；LeCun的JEPA和世界模型路线则仍在研究阶段，尚未产生同等量级的应用。但LeCun的批判迫使整个行业正视LLM的固有局限，而Sutskever等核心人物的"转向"也表明，AI的下一代架构可能真的会与今天的LLM大不相同。
