import React, { useState, useMemo, useCallback } from 'react';
import { Box, Paper, Typography, Chip, IconButton, Divider } from '@mui/material';
import { Close as CloseIcon, AccessTime, Error as ErrorIcon } from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';

// Task status type
export type TaskStatus = 'SUCCESS' | 'FAILED' | 'RUNNING' | 'PENDING' | 'SKIPPED' | 'UPSTREAM_FAILED';

// Task interface for DAG visualization
export interface Task {
  task_key: string;
  start_time?: string | null;
  end_time?: string | null;
  duration_seconds?: number | null;
  result_state?: TaskStatus | string | null;
  error_message?: string | null;
  cluster_id?: string | null;
  depends_on?: string[];
  attempt_number?: number;
  run_id?: string;
}

// Props for TaskDAG component
export interface TaskDAGProps {
  tasks: Task[];
  onTaskClick?: (task: Task) => void;
  selectedTaskKey?: string | null;
  width?: number;
  height?: number;
}

// Props for TaskDetails panel
export interface TaskDetailsProps {
  task: Task | null;
  onClose: () => void;
}

// Status colors
const STATUS_COLORS: Record<string, string> = {
  SUCCESS: '#4caf50',
  FAILED: '#f44336',
  RUNNING: '#ffc107',
  PENDING: '#9e9e9e',
  SKIPPED: '#607d8b',
  UPSTREAM_FAILED: '#ff9800',
};

// Get color for a task status
const getStatusColor = (status?: string | null): string => {
  if (!status) return STATUS_COLORS.PENDING;
  return STATUS_COLORS[status.toUpperCase()] || STATUS_COLORS.PENDING;
};

// Format duration in human-readable format
const formatDuration = (seconds?: number | null): string => {
  if (seconds === null || seconds === undefined) return 'N/A';
  if (seconds < 60) return `${Math.round(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
};

// Format timestamp
const formatTimestamp = (timestamp?: string | null): string => {
  if (!timestamp) return 'N/A';
  try {
    return new Date(timestamp).toLocaleString();
  } catch {
    return timestamp;
  }
};

// Node dimensions
const NODE_WIDTH = 160;
const NODE_HEIGHT = 80;
const NODE_MARGIN_X = 60;
const NODE_MARGIN_Y = 30;
const PADDING = 40;

// Calculate node positions using a simple horizontal layout
interface NodePosition {
  x: number;
  y: number;
  level: number;
  task: Task;
}

const calculateNodePositions = (tasks: Task[]): Map<string, NodePosition> => {
  const positions = new Map<string, NodePosition>();
  const taskMap = new Map(tasks.map(t => [t.task_key, t]));

  // Calculate levels (topological sort)
  const levels = new Map<string, number>();
  const visited = new Set<string>();

  const calculateLevel = (taskKey: string): number => {
    if (levels.has(taskKey)) return levels.get(taskKey)!;
    if (visited.has(taskKey)) return 0; // Cycle detected, treat as level 0

    visited.add(taskKey);
    const task = taskMap.get(taskKey);
    if (!task || !task.depends_on || task.depends_on.length === 0) {
      levels.set(taskKey, 0);
      return 0;
    }

    const maxParentLevel = Math.max(
      ...task.depends_on.map(dep => {
        if (taskMap.has(dep)) {
          return calculateLevel(dep);
        }
        return -1;
      })
    );

    const level = maxParentLevel + 1;
    levels.set(taskKey, level);
    return level;
  };

  tasks.forEach(task => calculateLevel(task.task_key));

  // Group tasks by level
  const levelGroups = new Map<number, Task[]>();
  tasks.forEach(task => {
    const level = levels.get(task.task_key) || 0;
    if (!levelGroups.has(level)) {
      levelGroups.set(level, []);
    }
    levelGroups.get(level)!.push(task);
  });

  // Calculate positions
  const sortedLevels = Array.from(levelGroups.keys()).sort((a, b) => a - b);

  sortedLevels.forEach(level => {
    const tasksAtLevel = levelGroups.get(level) || [];
    const totalHeight = tasksAtLevel.length * (NODE_HEIGHT + NODE_MARGIN_Y) - NODE_MARGIN_Y;
    const startY = (tasksAtLevel.length - 1) * (NODE_HEIGHT + NODE_MARGIN_Y) / 2;

    tasksAtLevel.forEach((task, index) => {
      positions.set(task.task_key, {
        x: PADDING + level * (NODE_WIDTH + NODE_MARGIN_X),
        y: PADDING + startY - index * (NODE_HEIGHT + NODE_MARGIN_Y) + totalHeight / 2,
        level,
        task,
      });
    });
  });

  return positions;
};

// Calculate SVG dimensions
const calculateSVGDimensions = (positions: Map<string, NodePosition>): { width: number; height: number } => {
  let maxX = 0;
  let maxY = 0;

  positions.forEach(pos => {
    maxX = Math.max(maxX, pos.x + NODE_WIDTH);
    maxY = Math.max(maxY, pos.y + NODE_HEIGHT);
  });

  return {
    width: maxX + PADDING,
    height: maxY + PADDING,
  };
};

// TaskDetails Panel Component
export const TaskDetailsPanel: React.FC<TaskDetailsProps> = ({ task, onClose }) => {
  if (!task) return null;

  const statusColor = getStatusColor(task.result_state);

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 20 }}
        transition={{ duration: 0.2 }}
      >
        <Paper
          elevation={8}
          sx={{
            position: 'absolute',
            right: 16,
            top: 16,
            width: 320,
            maxHeight: 'calc(100% - 32px)',
            overflow: 'auto',
            bgcolor: 'background.paper',
            borderRadius: 2,
            border: '1px solid',
            borderColor: 'divider',
          }}
        >
          {/* Header */}
          <Box
            sx={{
              p: 2,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              bgcolor: 'grey.900',
              borderBottom: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Typography variant="h6" sx={{ fontWeight: 600, color: 'white' }}>
              Task Details
            </Typography>
            <IconButton size="small" onClick={onClose} sx={{ color: 'grey.400' }}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Content */}
          <Box sx={{ p: 2 }}>
            {/* Task Key */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary">
                Task Key
              </Typography>
              <Typography variant="body1" sx={{ fontWeight: 500, fontFamily: 'monospace' }}>
                {task.task_key}
              </Typography>
            </Box>

            {/* Status */}
            <Box sx={{ mb: 2 }}>
              <Typography variant="caption" color="text.secondary">
                Result State
              </Typography>
              <Box sx={{ mt: 0.5 }}>
                <Chip
                  label={task.result_state || 'PENDING'}
                  size="small"
                  sx={{
                    bgcolor: statusColor,
                    color: 'white',
                    fontWeight: 600,
                  }}
                />
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Timing */}
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <AccessTime fontSize="small" color="action" />
                <Typography variant="subtitle2" color="text.secondary">
                  Timing
                </Typography>
              </Box>

              <Box sx={{ display: 'grid', gap: 1.5 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Start Time
                  </Typography>
                  <Typography variant="body2">
                    {formatTimestamp(task.start_time)}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    End Time
                  </Typography>
                  <Typography variant="body2">
                    {formatTimestamp(task.end_time)}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Duration
                  </Typography>
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    {formatDuration(task.duration_seconds)}
                  </Typography>
                </Box>
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Cluster Info */}
            {task.cluster_id && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Cluster ID
                </Typography>
                <Typography
                  variant="body2"
                  sx={{
                    fontFamily: 'monospace',
                    fontSize: '0.75rem',
                    wordBreak: 'break-all',
                  }}
                >
                  {task.cluster_id}
                </Typography>
              </Box>
            )}

            {/* Dependencies */}
            {task.depends_on && task.depends_on.length > 0 && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Dependencies
                </Typography>
                <Box sx={{ mt: 0.5, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                  {task.depends_on.map(dep => (
                    <Chip
                      key={dep}
                      label={dep}
                      size="small"
                      variant="outlined"
                      sx={{ fontSize: '0.7rem' }}
                    />
                  ))}
                </Box>
              </Box>
            )}

            {/* Attempt Number */}
            {task.attempt_number !== undefined && (
              <Box sx={{ mb: 2 }}>
                <Typography variant="caption" color="text.secondary">
                  Attempt Number
                </Typography>
                <Typography variant="body2">{task.attempt_number}</Typography>
              </Box>
            )}

            {/* Error Message */}
            {task.error_message && (
              <>
                <Divider sx={{ my: 2 }} />
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <ErrorIcon fontSize="small" color="error" />
                    <Typography variant="subtitle2" color="error">
                      Error Message
                    </Typography>
                  </Box>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 1.5,
                      bgcolor: 'error.dark',
                      borderColor: 'error.main',
                      maxHeight: 150,
                      overflow: 'auto',
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        color: 'error.contrastText',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {task.error_message}
                    </Typography>
                  </Paper>
                </Box>
              </>
            )}
          </Box>
        </Paper>
      </motion.div>
    </AnimatePresence>
  );
};

// TaskNode component for rendering individual task nodes
interface TaskNodeProps {
  task: Task;
  x: number;
  y: number;
  isSelected: boolean;
  onClick: () => void;
}

const TaskNode: React.FC<TaskNodeProps> = ({ task, x, y, isSelected, onClick }) => {
  const statusColor = getStatusColor(task.result_state);
  const isRunning = task.result_state?.toUpperCase() === 'RUNNING';

  return (
    <g
      transform={`translate(${x}, ${y})`}
      onClick={onClick}
      style={{ cursor: 'pointer' }}
    >
      {/* Selection highlight */}
      {isSelected && (
        <rect
          x={-4}
          y={-4}
          width={NODE_WIDTH + 8}
          height={NODE_HEIGHT + 8}
          rx={12}
          ry={12}
          fill="none"
          stroke="#2196f3"
          strokeWidth={3}
          strokeDasharray={isRunning ? '8,4' : 'none'}
        >
          {isRunning && (
            <animate
              attributeName="stroke-dashoffset"
              values="0;24"
              dur="1s"
              repeatCount="indefinite"
            />
          )}
        </rect>
      )}

      {/* Node background */}
      <rect
        width={NODE_WIDTH}
        height={NODE_HEIGHT}
        rx={8}
        ry={8}
        fill="#1e1e2f"
        stroke={statusColor}
        strokeWidth={2}
      />

      {/* Status indicator bar */}
      <rect
        y={0}
        width={NODE_WIDTH}
        height={4}
        rx={4}
        fill={statusColor}
      />

      {/* Running animation */}
      {isRunning && (
        <rect
          y={0}
          width={NODE_WIDTH / 3}
          height={4}
          rx={2}
          fill="#fff"
          opacity={0.6}
        >
          <animate
            attributeName="x"
            values={`0;${NODE_WIDTH * 2 / 3}`}
            dur="1.5s"
            repeatCount="indefinite"
          />
        </rect>
      )}

      {/* Task name */}
      <text
        x={NODE_WIDTH / 2}
        y={28}
        textAnchor="middle"
        fill="#ffffff"
        fontSize={12}
        fontWeight={600}
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        {task.task_key.length > 18
          ? task.task_key.substring(0, 16) + '...'
          : task.task_key}
      </text>

      {/* Duration */}
      <text
        x={NODE_WIDTH / 2}
        y={48}
        textAnchor="middle"
        fill="#9e9e9e"
        fontSize={10}
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        {formatDuration(task.duration_seconds)}
      </text>

      {/* Status badge */}
      <g transform={`translate(${NODE_WIDTH / 2}, 65)`}>
        <rect
          x={-30}
          y={-8}
          width={60}
          height={16}
          rx={8}
          fill={statusColor}
          opacity={0.2}
        />
        <text
          textAnchor="middle"
          y={4}
          fill={statusColor}
          fontSize={9}
          fontWeight={600}
          fontFamily="system-ui, -apple-system, sans-serif"
        >
          {(task.result_state || 'PENDING').toUpperCase()}
        </text>
      </g>
    </g>
  );
};

// Edge component for rendering dependency arrows
interface EdgeProps {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  isHighlighted?: boolean;
}

const Edge: React.FC<EdgeProps> = ({ fromX, fromY, toX, toY, isHighlighted }) => {
  // Path from right side of source to left side of target
  const startX = fromX + NODE_WIDTH;
  const startY = fromY + NODE_HEIGHT / 2;
  const endX = toX;
  const endY = toY + NODE_HEIGHT / 2;

  const path = `M ${startX} ${startY} C ${startX + 30} ${startY}, ${endX - 30} ${endY}, ${endX} ${endY}`;

  return (
    <g>
      {/* Edge line */}
      <path
        d={path}
        fill="none"
        stroke={isHighlighted ? '#2196f3' : '#4a4a5a'}
        strokeWidth={isHighlighted ? 2 : 1.5}
        markerEnd="url(#arrowhead)"
        opacity={isHighlighted ? 1 : 0.6}
      />
    </g>
  );
};

// Main TaskDAG Component
export const TaskDAG: React.FC<TaskDAGProps> = ({
  tasks,
  onTaskClick,
  selectedTaskKey,
  width: propWidth,
  height: propHeight,
}) => {
  const [internalSelectedTask, setInternalSelectedTask] = useState<string | null>(null);

  const effectiveSelectedKey = selectedTaskKey !== undefined ? selectedTaskKey : internalSelectedTask;

  // Calculate node positions
  const nodePositions = useMemo(() => calculateNodePositions(tasks), [tasks]);

  // Calculate SVG dimensions
  const dimensions = useMemo(() => calculateSVGDimensions(nodePositions), [nodePositions]);

  const svgWidth = propWidth || Math.max(dimensions.width, 400);
  const svgHeight = propHeight || Math.max(dimensions.height, 300);

  // Handle task click
  const handleTaskClick = useCallback((task: Task) => {
    setInternalSelectedTask(task.task_key);
    if (onTaskClick) {
      onTaskClick(task);
    }
  }, [onTaskClick]);

  // Get selected task for details panel
  const selectedTask = useMemo(() => {
    if (!effectiveSelectedKey) return null;
    return tasks.find(t => t.task_key === effectiveSelectedKey) || null;
  }, [tasks, effectiveSelectedKey]);

  // Calculate edges
  const edges = useMemo(() => {
    const result: { from: string; to: string; fromPos: NodePosition; toPos: NodePosition }[] = [];

    tasks.forEach(task => {
      if (task.depends_on) {
        task.depends_on.forEach(dep => {
          const fromPos = nodePositions.get(dep);
          const toPos = nodePositions.get(task.task_key);

          if (fromPos && toPos) {
            result.push({
              from: dep,
              to: task.task_key,
              fromPos,
              toPos,
            });
          }
        });
      }
    });

    return result;
  }, [tasks, nodePositions]);

  if (tasks.length === 0) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          height: 200,
          color: 'text.secondary',
        }}
      >
        <Typography>No tasks to display</Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ position: 'relative', width: '100%', height: '100%' }}>
      <Box
        sx={{
          width: '100%',
          height: '100%',
          overflow: 'auto',
          bgcolor: '#0d0d1a',
          borderRadius: 2,
          border: '1px solid',
          borderColor: 'divider',
        }}
      >
        <svg
          width={svgWidth}
          height={svgHeight}
          style={{ display: 'block', minWidth: '100%' }}
        >
          {/* Definitions */}
          <defs>
            {/* Arrowhead marker */}
            <marker
              id="arrowhead"
              markerWidth={10}
              markerHeight={7}
              refX={9}
              refY={3.5}
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#4a4a5a" />
            </marker>

            {/* Highlighted arrowhead */}
            <marker
              id="arrowhead-highlighted"
              markerWidth={10}
              markerHeight={7}
              refX={9}
              refY={3.5}
              orient="auto"
            >
              <polygon points="0 0, 10 3.5, 0 7" fill="#2196f3" />
            </marker>

            {/* Grid pattern for background */}
            <pattern
              id="grid"
              width={40}
              height={40}
              patternUnits="userSpaceOnUse"
            >
              <path
                d="M 40 0 L 0 0 0 40"
                fill="none"
                stroke="#1a1a2e"
                strokeWidth={1}
              />
            </pattern>
          </defs>

          {/* Background grid */}
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Render edges */}
          <g className="edges">
            {edges.map((edge, index) => (
              <Edge
                key={`${edge.from}-${edge.to}-${index}`}
                fromX={edge.fromPos.x}
                fromY={edge.fromPos.y}
                toX={edge.toPos.x}
                toY={edge.toPos.y}
                isHighlighted={
                  effectiveSelectedKey === edge.from ||
                  effectiveSelectedKey === edge.to
                }
              />
            ))}
          </g>

          {/* Render nodes */}
          <g className="nodes">
            {Array.from(nodePositions.entries()).map(([taskKey, pos]) => (
              <TaskNode
                key={taskKey}
                task={pos.task}
                x={pos.x}
                y={pos.y}
                isSelected={effectiveSelectedKey === taskKey}
                onClick={() => handleTaskClick(pos.task)}
              />
            ))}
          </g>
        </svg>
      </Box>

      {/* Task Details Panel */}
      <TaskDetailsPanel
        task={selectedTask}
        onClose={() => {
          setInternalSelectedTask(null);
          if (onTaskClick) {
            onTaskClick(null as unknown as Task);
          }
        }}
      />
    </Box>
  );
};

// Default export
export default TaskDAG;
