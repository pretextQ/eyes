import {
  Activity,
  CircleHelp,
  FlaskConical,
  GitCompareArrows,
  Layers3,
  SlidersHorizontal,
  Target,
} from "lucide-react";

export const navigation = [
  {
    url: "/observe",
    text: "Agent 观测",
    en: "Observation",
    icon: Activity,
    group: "执行观测",
    description: "在 Agent 中对话，实时查看模型与工具调用",
  },
  {
    url: "/experiments",
    text: "实验",
    en: "Experiments",
    icon: FlaskConical,
    group: "实验与审阅",
    description: "运行测试，查看用例与执行证据",
  },
  {
    url: "/batches",
    text: "多 Agent 批次",
    en: "Agent batches",
    icon: Layers3,
    group: "实验与审阅",
    description: "为多个 Agent 配置测试集与并发任务，集中跟踪进度",
  },
  {
    url: "/comparison",
    text: "回归报告",
    en: "Comparison",
    icon: GitCompareArrows,
    group: "实验与审阅",
    description: "查看固定回归结论、门槛与执行证据",
  },
  {
    url: "/targets",
    text: "目标 Agent",
    en: "Targets",
    icon: Target,
    group: "版本与配置",
    description: "管理 Agent 接入方式与版本",
  },
  {
    url: "/datasets",
    text: "测试集",
    en: "Datasets",
    icon: Layers3,
    group: "版本与配置",
    description: "导入 JSONL，管理测试用例",
  },
  {
    url: "/scorers",
    text: "评分口径",
    en: "Scorers",
    icon: SlidersHorizontal,
    group: "版本与配置",
    description: "发布评分规则与证据要求",
  },
  {
    url: "/operations",
    text: "运行状态",
    en: "Operations",
    icon: Activity,
    group: "工作空间",
    description: "检查 Runner、工作队列与服务状态",
  },
  {
    url: "/guide",
    text: "接入指南",
    en: "Guide",
    icon: CircleHelp,
    group: "工作空间",
    description: "了解接入步骤与观测范围",
  },
];

export const navigationGroups = [
  ...new Set(navigation.map((item) => item.group)),
];
