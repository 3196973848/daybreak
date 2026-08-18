import {
  createContext, createElement, useCallback, useContext, useMemo, useState,
} from 'react'
import type { ReactNode } from 'react'


export type Lang = 'zh' | 'en'
type Params = Record<string, string | number>

export const dict: Record<string, [string, string]> = {
  back: ['返回', 'Back'],
  loading: ['加载中…', 'Loading…'],
  verified: ['已验证', 'Verified'],
  close: ['关闭', 'Close'],
  cancel: ['取消', 'Cancel'],

  homeEyebrow: ['停止空想 · 开始行动', 'Stop dreaming · Start doing'],
  homeTitle: ['把模糊的愿景，变成每一天的行动', 'Turn vague visions into daily actions'],
  homeSub: ['AI 帮你把大目标拆成里程碑和每日任务，排出具体日程——不用再纠结从哪开始，每天都有下一步可做。', 'AI breaks your big goals into milestones and a day-by-day schedule — stop wondering where to start, every day has a concrete next step.'],
  today: ['今天', 'today'],
  goalTitle: ['目标标题 *', 'Goal title *'],
  goalTitlePlaceholder: ['例如：3个月从零学会Python编程', 'e.g. Learn Python in 3 months'],
  goalDesc: ['补充说明（可选）', 'Details (optional)'],
  goalDescPlaceholder: ['想达到什么程度？有什么约束？', 'What level? Any constraints?'],
  durationLabel: ['预期完成时间', 'Expected duration'],
  dailyHoursLabel: ['每日可投入时间', 'Daily hours'],
  durationHelp: ['任务会从今天起（包含周末）均匀安排在这段时间内。', 'Tasks are spread evenly across this period, including weekends.'],
  dailyHoursHelp: ['单位：小时，支持 0.5 的倍数。', 'Hours, in 0.5 steps.'],
  generate: ['生成计划', 'Generate plan'],
  generating: ['AI 正在拆解计划…', 'AI is planning…'],
  history: ['历史目标', 'Past goals'],
  delete: ['删除', 'Delete'],
  open: ['打开', 'Open'],
  due: ['截止', 'Due'],
  created: ['创建于', 'Created'],
  dueLabel: ['截止 {date}', 'Due {date}'],
  createdLabel: ['创建于 {date}', 'Created {date}'],
  doneCount: ['{done}/{total} 完成', '{done}/{total} done'],
  durationError: ['预期完成时间必须是正整数', 'Expected duration must be a positive integer'],
  dailyHoursError: ['每日可投入时间必须是 0.5 小时的正数倍', 'Daily hours must be a positive multiple of 0.5'],
  unitDay: ['天', 'days'],
  unitWeek: ['周', 'weeks'],
  unitMonth: ['月', 'months'],
  timeUnit: ['时间单位', 'Time unit'],
  capacityError: [
    '当前时间不足：计划约需 {required} 小时，现有周期可用 {available} 小时。建议至少设置 {days} 天，或提高每日投入时间。',
    'Not enough time: the plan needs ~{required} hours but the period only allows {available}. Set at least {days} days or raise your daily hours.',
  ],
  genericError: ['生成失败，请重试', 'Generation failed, please retry'],
  deleteFailed: ['删除失败', 'Delete failed'],
  failedLoad: ['加载失败', 'Failed to load'],
  actionFailed: ['操作失败', 'Operation failed'],
  invalidTask: ['任务编号无效', 'Invalid task id'],
  loadSessionFailed: ['加载学习记录失败', 'Failed to load learning history'],
  createSessionFailed: ['创建学习会话失败', 'Failed to create learning session'],
  verificationNotReady: ['检验内容尚未加载，无法提交', 'Verification is not ready yet'],
  submitFailed: ['提交失败', 'Submit failed'],
  saveFailed: ['保存失败', 'Save failed'],

  overviewEyebrow: ['计划总览', 'Plan overview'],
  dailyTasks: ['每日任务', 'Daily tasks'],
  progressLabel: ['整体进度', 'Overall progress'],
  strategy: ['策略', 'Strategy'],
  milestone: ['里程碑', 'Milestone'],
  done: ['已完成', 'Done'],
  inProgress: ['进行中', 'In progress'],
  notStarted: ['未开始', 'Not started'],
  doneSuffix: ['完成', 'done'],
  exportCalendar: ['导出日历', 'Export calendar'],
  noPlan: ['此目标未生成计划（可能生成失败），请返回删除后重试。', 'No plan was generated for this goal; go back, delete it, and retry.'],
  noStageTasks: ['此阶段暂无任务', 'No tasks in this stage'],
  strategyLabel: ['策略：{strategy}', 'Strategy: {strategy}'],

  dailyEyebrow: ['每日任务', 'Daily tasks'],
  clickToComplete: ['点击任务左侧圆点，标记完成', 'Click the dot to mark complete'],
  noTasksDay: ['这一天没有安排任务，换个日期看看', 'No tasks on this day — pick another date'],
  hoursShort: ['约 {n} 小时', '~{n}h'],
  hoursValue: ['{n} 小时', '{n} hours'],
  weekSun: ['周日', 'Sun'],
  weekMon: ['周一', 'Mon'],
  weekTue: ['周二', 'Tue'],
  weekWed: ['周三', 'Wed'],
  weekThu: ['周四', 'Thu'],
  weekFri: ['周五', 'Fri'],
  weekSat: ['周六', 'Sat'],
  unscheduled: ['未排期', 'Unscheduled'],
  markDone: ['标记完成', 'Mark complete'],
  markUndone: ['标记未完成', 'Mark incomplete'],
  verify: ['检验', 'Verify'],
  startLearning: ['开始学习', 'Start learning'],
  continueLearning: ['继续学习', 'Continue learning'],
  typeLearn: ['学习', 'Learn'],
  typePractice: ['实操', 'Practice'],
  typeProject: ['项目', 'Project'],
  calendarLegend: ['• 当天有任务', '• tasks today'],
  calendarMonth: ['{year}年{month}月', '{month}/{year}'],
  prevMonth: ['上个月', 'Previous month'],
  nextMonth: ['下个月', 'Next month'],

  tutorEyebrow: ['AI 导师', 'AI tutor'],
  modelLabel: ['模型', 'Model'],
  learningStatus: ['学习状态', 'Learning status'],
  currentStage: ['当前阶段', 'Current stage'],
  estHours: ['预计时长', 'Est. hours'],
  covered: ['已掌握', 'Covered'],
  weak: ['待加强', 'Needs work'],
  noCovered: ['尚未记录', 'Not recorded yet'],
  noWeak: ['暂未发现', 'None found'],
  readyHint: ['建议开始检验', 'Suggested: verify'],
  startVerify: ['开始检验', 'Start verification'],
  verificationPassed: ['检验已通过', 'Verification passed'],
  replyLabel: ['回复导师', 'Reply to tutor'],
  replyPlaceholder: ['Enter 发送，Shift+Enter 换行', 'Enter to send · Shift+Enter for newline'],
  youLabel: ['你', 'You'],
  tutorLabel: ['导师', 'Tutor'],
  tutorSessionTitle: ['导师学习', 'Tutor session'],
  stageLabel: ['学习阶段', 'Learning stage'],
  chatLabel: ['导师对话', 'Tutor chat'],
  send: ['发送', 'Send'],
  sending: ['发送中', 'Sending'],
  retry: ['重试', 'Retry'],
  stageDiagnose: ['诊断', 'Diagnose'],
  stageExplain: ['讲解', 'Explain'],
  stagePractice: ['练习', 'Practice'],
  stageRemediate: ['补强', 'Remediate'],
  stageReady: ['已准备好', 'Ready'],
  livePreparing: ['导师正在准备诊断问题', 'The tutor is preparing a diagnostic question'],
  liveThinking: ['导师正在思考', 'The tutor is thinking'],
  liveLoading: ['正在加载学习记录', 'Loading learning history'],

  verifyTitle: ['检验 · {t}', 'Verify · {t}'],
  testSub: ['测试模式 · 答对 70% 即通过', 'Test mode · pass at 70%'],
  deliverSub: ['交付模式 · 提交成果描述，评审是否达标', 'Delivery · submit a description for review'],
  generatingTest: ['正在生成 10 道题', 'Generating 10 questions'],
  generatingCriteria: ['正在生成验收标准', 'Generating acceptance criteria'],
  generatingInProgress: ['生成中', 'Generating'],
  submitTest: ['提交检验', 'Submit answers'],
  submitDeliver: ['提交评审', 'Submit review'],
  reviewing: ['AI 评审中…', 'AI is reviewing…'],
  regenerate: ['重新生成', 'Regenerate'],
  total: ['总分', 'Total'],
  totalScore: ['总分：{points} / 100', 'Total: {points} / 100'],
  score: ['得分', 'Score'],
  scorePct: ['得分：{score}%', 'Score: {score}%'],
  correctAnswer: ['正确答案', 'Correct answer'],
  questionNo: ['第 {n} 题', 'Q{n}'],
  correct: ['正确', 'Correct'],
  wrong: ['错误', 'Wrong'],
  points: ['{n} 分', '{n} pts'],
  pointsPer: ['{n} / 10 分', '{n} / 10 pts'],
  acceptance: ['验收标准', 'Acceptance criteria'],
  writeAnswer: ['写下你的回答…', 'Write your answer…'],
  submissionPlaceholder: ['填写你的实现成果 / 代码链接 / 说明……', 'Describe your result, code link, notes…'],
  passed: ['✓ 检验通过', '✓ Passed'],
  failed: ['✗ 未通过', '✗ Failed'],

  setupEyebrow: ['首次设置', 'First-time setup'],
  setupTitle: ['选择你的 AI 提供方', 'Choose your AI provider'],
  setupSub: ['填入 API Key 后即可开始；Key 只保存在本机配置文件中。', 'Add your API key to start; it is stored only in the local config.'],
  needsKey: ['需要 API Key', 'API key required'],
  localNoKey: ['本地运行，无需 Key', 'Runs locally, no key'],
  apiKey: ['API Key', 'API Key'],
  baseUrl: ['Base URL（OpenAI 兼容）', 'Base URL (OpenAI-compatible)'],
  defaultModel: ['默认模型', 'Default model'],
  saveStart: ['保存并开始', 'Save & start'],
  saving: ['保存中…', 'Saving…'],
  keyRequired: ['请填写 API Key', 'Please enter an API key'],

  progressCount: ['{done} / {total} · {pct}%', '{done} / {total} · {pct}%'],
  progressAria: ['已完成 {pct}%', '{pct}% complete'],

  logout: ['退出', 'Log out'],
  switchLang: ['English', '中文'],
}


interface I18nState {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: string, params?: Params) => string
}

function translate(lang: Lang, key: string, params?: Params): string {
  const pair = dict[key]
  let text = pair ? pair[lang === 'zh' ? 0 : 1] : key
  if (params) {
    for (const [name, value] of Object.entries(params)) {
      text = text.replace(`{${name}}`, String(value))
    }
  }
  return text
}

// Default context keeps zh so components render Chinese even without a provider
// (used by tests and by SSR-free fallbacks).
const I18nContext = createContext<I18nState>({
  lang: 'zh',
  setLang: () => undefined,
  t: (key, params) => translate('zh', key, params),
})


export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => (
    localStorage.getItem('planagent_lang') === 'en' ? 'en' : 'zh'
  ))

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    localStorage.setItem('planagent_lang', next)
  }, [])

  const t = useCallback((key: string, params?: Params) => {
    return translate(lang, key, params)
  }, [lang])

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])
  return createElement(I18nContext.Provider, { value }, children)
}


export function useI18n(): I18nState {
  return useContext(I18nContext)
}
