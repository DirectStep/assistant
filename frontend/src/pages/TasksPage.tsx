import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  pointerWithin,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'

import { completeTask, createTask, deleteTask, getTasks, moveTask, updateTask } from '../api/tasks'
import { KanbanColumn } from '../components/KanbanColumn'
import { TaskCard } from '../components/TaskCard'
import { TaskSheet } from '../components/TaskSheet'
import type { Task, TaskInput, TaskStatus } from '../types/task'

const columns: { status: TaskStatus; title: string }[] = [
  { status: 'inbox', title: 'Входящие' },
  { status: 'today', title: 'Сегодня' },
  { status: 'week', title: 'На неделе' },
  { status: 'later', title: 'Позже' },
  { status: 'done', title: 'Готово' },
]

type ViewMode = 'kanban' | 'matrix'
type MatrixQuadrant = 'importantUrgent' | 'importantLater' | 'urgentRoutine' | 'laterRoutine'

const matrixQuadrants: { key: MatrixQuadrant; title: string; description: string }[] = [
  { key: 'importantUrgent', title: 'Сделать сейчас', description: 'Важно и срочно' },
  { key: 'importantLater', title: 'Запланировать', description: 'Важно, не срочно' },
  { key: 'urgentRoutine', title: 'Решить быстро', description: 'Срочно, обычная важность' },
  { key: 'laterRoutine', title: 'Позже', description: 'Не срочно' },
]

function isUrgent(task: Task) {
  if (task.status === 'today') return true
  if (!task.due_at) return false

  const endOfToday = new Date()
  endOfToday.setHours(23, 59, 59, 999)
  return new Date(task.due_at) <= endOfToday
}

function getMatrixQuadrant(task: Task): MatrixQuadrant {
  const important = task.importance === 'important'
  const urgent = isUrgent(task)
  if (important && urgent) return 'importantUrgent'
  if (important) return 'importantLater'
  if (urgent) return 'urgentRoutine'
  return 'laterRoutine'
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Доброе утро'
  if (hour < 18) return 'Добрый день'
  return 'Добрый вечер'
}

export function TasksPage() {
  const queryClient = useQueryClient()
  const [sheetOpen, setSheetOpen] = useState(false)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(() => (
    window.localStorage.getItem('tasks-view') === 'matrix' ? 'matrix' : 'kanban'
  ))
  const kanbanRef = useRef<HTMLDivElement>(null)
  const sensors = useSensors(
    useSensor(KeyboardSensor),
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
  )
  const tasksQuery = useQuery({ queryKey: ['tasks'], queryFn: getTasks })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['tasks'] })
  const createMutation = useMutation({
    mutationFn: createTask,
    onSuccess: () => { void refresh(); setSheetOpen(false) },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: Partial<TaskInput> }) => updateTask(id, data),
    onSuccess: () => { void refresh(); setSheetOpen(false) },
  })
  const moveMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: TaskStatus }) => moveTask(id, status),
    onSuccess: refresh,
  })
  const completeMutation = useMutation({
    mutationFn: completeTask,
    onSuccess: () => { void refresh(); setSheetOpen(false) },
  })
  const deleteMutation = useMutation({
    mutationFn: deleteTask,
    onSuccess: () => { void refresh(); setSheetOpen(false) },
  })
  const tasks = useMemo(() => tasksQuery.data ?? [], [tasksQuery.data])
  const grouped = useMemo(
    () => Object.fromEntries(
      columns.map(({ status }) => [status, tasks.filter((task) => task.status === status)]),
    ) as Record<TaskStatus, Task[]>,
    [tasks],
  )
  const matrixGroups = useMemo(() => {
    const groups: Record<MatrixQuadrant, Task[]> = {
      importantUrgent: [],
      importantLater: [],
      urgentRoutine: [],
      laterRoutine: [],
    }
    tasks.filter((task) => task.status !== 'done').forEach((task) => {
      groups[getMatrixQuadrant(task)].push(task)
    })
    return groups
  }, [tasks])
  const activeCount = tasks.filter((task) => task.status !== 'done').length
  const todayCount = grouped.today.length
  const overdueCount = tasks.filter(
    (task) => task.status !== 'done' && task.due_at && new Date(task.due_at) < new Date(),
  ).length
  const busy = createMutation.isPending || updateMutation.isPending || completeMutation.isPending || deleteMutation.isPending
  const error = tasksQuery.error || createMutation.error || updateMutation.error || moveMutation.error || completeMutation.error || deleteMutation.error

  useEffect(() => {
    const board = kanbanRef.current
    if (!board || viewMode !== 'kanban') return

    const handleWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return
      const maxScrollLeft = board.scrollWidth - board.clientWidth
      const canMove = event.deltaY > 0 ? board.scrollLeft < maxScrollLeft : board.scrollLeft > 0
      if (!canMove) return
      event.preventDefault()
      board.scrollLeft += event.deltaY
    }

    board.addEventListener('wheel', handleWheel, { passive: false })
    return () => board.removeEventListener('wheel', handleWheel)
  }, [viewMode])

  function selectView(mode: ViewMode) {
    setViewMode(mode)
    window.localStorage.setItem('tasks-view', mode)
  }

  function scrollKanban(direction: -1 | 1) {
    const board = kanbanRef.current
    if (!board) return
    board.scrollBy({ left: direction * board.clientWidth * 0.88, behavior: 'smooth' })
  }

  function handleDragEnd(event: DragEndEvent) {
    const target = event.over?.id as TaskStatus | undefined
    const taskId = event.active.data.current?.taskId as number | undefined
    if (!target || !taskId) return
    const task = tasks.find((item) => item.id === taskId)
    if (task && task.status !== target) moveMutation.mutate({ id: taskId, status: target })
  }

  return (
    <main className="tasks-page">
      <header className="page-header">
        <div>
          <p>{new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long', weekday: 'long' }).format(new Date())}</p>
          <h1>{greeting()}</h1>
        </div>
        <button className="add-button" type="button" onClick={() => { setSelectedTask(null); setSheetOpen(true) }}>+ Новая</button>
      </header>

      <section className="day-strip" aria-label="Сводка по задачам">
        <div><strong>{activeCount}</strong><span>активных</span></div>
        <div><strong>{todayCount}</strong><span>сегодня</span></div>
        <div className={overdueCount ? 'has-alert' : ''}><strong>{overdueCount}</strong><span>просрочено</span></div>
      </section>

      {error && !sheetOpen && <div className="error-banner">Не удалось синхронизировать задачи. Проверь соединение.</div>}
      {tasksQuery.isLoading ? (
        <div className="loading-state">Загружаю задачи…</div>
      ) : (
        <>
          <div className="task-view-toolbar">
            <div className="view-switch" role="group" aria-label="Вид задач">
              <button className={viewMode === 'kanban' ? 'active' : ''} type="button" aria-pressed={viewMode === 'kanban'} onClick={() => selectView('kanban')}>Канбан</button>
              <button className={viewMode === 'matrix' ? 'active' : ''} type="button" aria-pressed={viewMode === 'matrix'} onClick={() => selectView('matrix')}>Матрица</button>
            </div>
            {viewMode === 'kanban' && (
              <div className="kanban-arrows" aria-label="Прокрутка колонок">
                <button type="button" aria-label="Предыдущая колонка" onClick={() => scrollKanban(-1)}>←</button>
                <button type="button" aria-label="Следующая колонка" onClick={() => scrollKanban(1)}>→</button>
              </div>
            )}
          </div>
          <DndContext
            sensors={sensors}
            collisionDetection={(args) => args.pointerCoordinates ? pointerWithin(args) : closestCenter(args)}
            autoScroll={{ acceleration: 8, interval: 16, threshold: { x: 0.12, y: 0.18 } }}
            onDragEnd={handleDragEnd}
          >
            {viewMode === 'kanban' ? (
              <div ref={kanbanRef} className="kanban-board" tabIndex={0} aria-label="Канбан-доска. Листайте горизонтально, чтобы увидеть все колонки.">
                {columns.map((column) => (
                  <KanbanColumn
                    key={column.status}
                    {...column}
                    tasks={grouped[column.status]}
                    onOpen={(task) => { setSelectedTask(task); setSheetOpen(true) }}
                  />
                ))}
              </div>
            ) : (
              <div className="eisenhower-matrix" aria-label="Матрица Эйзенхауэра">
                {matrixQuadrants.map((quadrant) => (
                  <section key={quadrant.key} className={`matrix-quadrant ${quadrant.key}`}>
                    <header>
                      <div><h2>{quadrant.title}</h2><p>{quadrant.description}</p></div>
                      <span>{matrixGroups[quadrant.key].length}</span>
                    </header>
                    <div className="matrix-task-list">
                      {matrixGroups[quadrant.key].map((task) => (
                        <TaskCard key={task.id} task={task} draggable={false} onOpen={() => { setSelectedTask(task); setSheetOpen(true) }} />
                      ))}
                      {matrixGroups[quadrant.key].length === 0 && <p className="matrix-empty">Пусто</p>}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </DndContext>
        </>
      )}

      {sheetOpen && (
        <TaskSheet
          task={selectedTask}
          busy={busy}
          error={Boolean(createMutation.error || updateMutation.error || completeMutation.error || deleteMutation.error)}
          onClose={() => setSheetOpen(false)}
          onSave={(data) => selectedTask
            ? updateMutation.mutate({ id: selectedTask.id, data })
            : createMutation.mutate(data)}
          onDelete={() => selectedTask && window.confirm('Удалить задачу?') && deleteMutation.mutate(selectedTask.id)}
          onComplete={() => selectedTask && completeMutation.mutate(selectedTask.id)}
        />
      )}
    </main>
  )
}
