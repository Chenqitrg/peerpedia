---
title: "Gradient Descent and Backpropagation: A Mathematical Derivation"
title_zh: "梯度下降与反向传播：数学推导"
abstract: "Lecture notes deriving gradient descent optimization and the backpropagation algorithm for training feedforward neural networks. Includes the chain rule derivation, common activation functions, and practical considerations."
abstract_zh: "课堂笔记：推导前馈神经网络训练的梯度下降优化和反向传播算法。包括链式法则推导、常用激活函数和实践考虑。"
categories:
  - computer-science
  - machine-learning
  - mathematics
keywords:
  - gradient descent
  - backpropagation
  - neural networks
  - optimization
language: bilingual
---

= 梯度下降与反向传播
= Gradient Descent and Backpropagation

== 1. 问题定义 / Problem Setup

给定训练数据集 $D = {(x_i, y_i)}_(i=1)^N$，我们希望找到参数 $theta in RR^p$
来最小化损失函数：

Given a training dataset $D = {(x_i, y_i)}_(i=1)^N$, we want to find
parameters $theta in RR^p$ that minimize the loss function:

$ J(theta) = 1/N sum_(i=1)^N L(f(x_i; theta), y_i) + lambda / 2 ||theta||^2 $

其中 $f$ 是神经网络函数，$L$ 是损失度量（如 MSE 或交叉熵），$lambda$ 是
L2 正则化系数。

Where $f$ is the neural network function, $L$ is the loss measure (e.g. MSE
or cross-entropy), and $lambda$ is the L2 regularization coefficient.

== 2. 梯度下降 / Gradient Descent

批量梯度下降更新规则：

The batch gradient descent update rule:

$ theta_(t+1) = theta_t - alpha nabla J(theta_t) $

其中学习率 $alpha > 0$ 控制步长。

Where the learning rate $alpha > 0$ controls the step size.

*收敛定理 / Convergence Theorem*:
若 $J$ 是 $L$-光滑的（即 $nabla J$ 是 $L$-Lipschitz 连续），梯度下降
满足：

If $J$ is $L$-smooth (i.e. $nabla J$ is $L$-Lipschitz continuous),
gradient descent satisfies:

$ J(theta_(t+1)) <= J(theta_t) - (1 - (alpha L)/2) alpha ||nabla J(theta_t)||^2 $

当 $alpha < 2/L$ 时保证下降。

Descent is guaranteed when $alpha < 2/L$.

== 3. 反向传播 / Backpropagation

考虑一个 $L$ 层前馈网络：

Consider an $L$-layer feedforward network:

$ a^(0) &= x $
$ z^(l) &= W^(l) a^(l-1) + b^(l) quad (l = 1, ..., L) $
$ a^(l) &= sigma(z^(l)) $

其中 $sigma$ 是激活函数（如 ReLU、sigmoid、tanh）。

Where $sigma$ is an activation function (e.g. ReLU, sigmoid, tanh).

*输出层误差 / Output Layer Error*:

$ delta^(L) = nabla_a L odot sigma'(z^(L)) $

*反向传播 / Backward Pass*:

$ delta^(l) = ((W^(l+1))^T delta^(l+1)) odot sigma'(z^(l)) $

*参数梯度 / Parameter Gradients*:

$ (partial J) / (partial W^(l)) &= delta^(l) (a^(l-1))^T $
$ (partial J) / (partial b^(l)) &= delta^(l) $

== 4. 常用激活函数 / Common Activation Functions

*Sigmoid*:
$ sigma(x) = 1 / (1 + e^(-x)), quad sigma'(x) = sigma(x)(1 - sigma(x)) $

*ReLU*:
$ "ReLU"(x) = max(0, x), quad "ReLU"'(x) = cases(0 " if " x < 0, 1 " if " x > 0) $

*Tanh*:
$ tanh(x) = (e^x - e^(-x)) / (e^x + e^(-x)), quad tanh'(x) = 1 - tanh^2(x) $

== 5. 实践技巧 / Practical Tips

- 使用 Xavier/He 初始化来保证信号传播 / Use Xavier/He initialization for signal propagation
- 批量归一化加速训练 / Batch normalization accelerates training
- 学习率衰减 / Learning rate decay: $alpha(t) = alpha_0 / (1 + beta t)$
- 早停防止过拟合 / Early stopping prevents overfitting
- 动量法加速收敛 / Momentum accelerates convergence:

  $ v_(t+1) = mu v_t - alpha nabla J(theta_t) $
  $ theta_(t+1) = theta_t + v_(t+1) $

== 参考文献 / References

#bibliography(
  [Rumelhart, D. E. et al. (1986). "Learning representations by back-propagating errors."],
  [Goodfellow, I., Bengio, Y., & Courville, A. (2016). "Deep Learning."],
  [Kingma, D. P. & Ba, J. (2015). "Adam: A Method for Stochastic Optimization."],
  [He, K. et al. (2015). "Delving Deep into Rectifiers."],
)
