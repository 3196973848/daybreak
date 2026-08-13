import type { TaskDTO } from '../types'

export function VerificationModal({ task, onClose }: { task: TaskDTO; onClose: () => void }) {
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }} onClick={onClose}>
      <div className="card" style={{ padding: 20, width: 400 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>检验 · {task.title}</strong>
          <button className="btn-ghost" onClick={onClose}>✕</button>
        </div>
        <p className="faint">加载检验内容中…</p>
      </div>
    </div>
  )
}
