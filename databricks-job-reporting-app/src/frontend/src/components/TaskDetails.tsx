import React from 'react';
import { Box, Paper, Typography, Chip, IconButton, Divider } from '@mui/material';
import { Close as CloseIcon, AccessTime, Error as ErrorIcon, Memory } from '@mui/icons-material';
import { motion, AnimatePresence } from 'framer-motion';

// Task status type
export type TaskStatus = 'SUCCESS' | 'FAILED' | 'RUNNING' | 'PENDING' | 'SKIPPED' | 'UPSTREAM_FAILED';

// Task interface
export interface TaskInfo {
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
  notebook_path?: string;
  python_file?: string;
  spark_jar_task?: {
    main_class_name?: string;
    jar_uri?: string;
  };
  spark_submit_task?: {
    parameters?: string[];
  };
  sql_task?: {
    query_id?: string;
    warehouse_id?: string;
  };
}

// Props for TaskDetails component
export interface TaskDetailsProps {
  task: TaskInfo | null;
  onClose: () => void;
  position?: 'right' | 'left' | 'bottom';
  showDependencies?: boolean;
  onDependencyClick?: (taskKey: string) => void;
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

// Detail row component
interface DetailRowProps {
  label: string;
  value: React.ReactNode;
  monospace?: boolean;
}

const DetailRow: React.FC<DetailRowProps> = ({ label, value, monospace }) => (
  <Box sx={{ mb: 1.5 }}>
    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.25 }}>
      {label}
    </Typography>
    <Typography
      variant="body2"
      sx={{
        fontFamily: monospace ? 'monospace' : 'inherit',
        fontSize: monospace ? '0.75rem' : 'inherit',
        wordBreak: 'break-word',
      }}
    >
      {value || 'N/A'}
    </Typography>
  </Box>
);

// Main TaskDetails component
export const TaskDetails: React.FC<TaskDetailsProps> = ({
  task,
  onClose,
  position = 'right',
  showDependencies = true,
  onDependencyClick,
}) => {
  if (!task) return null;

  const statusColor = getStatusColor(task.result_state);

  // Position styles based on position prop
  const getPositionStyles = () => {
    switch (position) {
      case 'left':
        return { left: 16, top: 16 };
      case 'bottom':
        return { left: 16, bottom: 16, right: 16, width: 'auto' };
      case 'right':
      default:
        return { right: 16, top: 16 };
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, x: position === 'left' ? -20 : 20 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: position === 'left' ? -20 : 20 }}
        transition={{ duration: 0.2 }}
        style={{ position: 'absolute', zIndex: 1000, ...getPositionStyles() }}
      >
        <Paper
          elevation={8}
          sx={{
            width: position === 'bottom' ? 'auto' : 340,
            maxHeight: position === 'bottom' ? 300 : 'calc(100% - 32px)',
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
              position: 'sticky',
              top: 0,
              zIndex: 1,
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <Typography variant="h6" sx={{ fontWeight: 600, color: 'white' }}>
                Task Details
              </Typography>
              <Chip
                label={task.result_state || 'PENDING'}
                size="small"
                sx={{
                  bgcolor: statusColor,
                  color: 'white',
                  fontWeight: 600,
                  fontSize: '0.7rem',
                }}
              />
            </Box>
            <IconButton size="small" onClick={onClose} sx={{ color: 'grey.400' }}>
              <CloseIcon fontSize="small" />
            </IconButton>
          </Box>

          {/* Content */}
          <Box sx={{ p: 2 }}>
            {/* Task Key */}
            <DetailRow
              label="Task Key"
              value={
                <Typography
                  variant="body1"
                  sx={{ fontWeight: 600, fontFamily: 'monospace', color: 'primary.main' }}
                >
                  {task.task_key}
                </Typography>
              }
            />

            {/* Run ID */}
            {task.run_id && (
              <DetailRow label="Run ID" value={task.run_id} monospace />
            )}

            <Divider sx={{ my: 2 }} />

            {/* Timing Section */}
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                <AccessTime fontSize="small" color="action" />
                <Typography variant="subtitle2" color="text.secondary">
                  Timing Information
                </Typography>
              </Box>

              <Box sx={{ pl: 3 }}>
                <DetailRow label="Start Time" value={formatTimestamp(task.start_time)} />
                <DetailRow label="End Time" value={formatTimestamp(task.end_time)} />
                <DetailRow
                  label="Duration"
                  value={
                    <Typography variant="body2" sx={{ fontWeight: 600, color: 'success.main' }}>
                      {formatDuration(task.duration_seconds)}
                    </Typography>
                  }
                />
              </Box>
            </Box>

            <Divider sx={{ my: 2 }} />

            {/* Cluster Section */}
            <Box sx={{ mb: 2 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
                <Memory fontSize="small" color="action" />
                <Typography variant="subtitle2" color="text.secondary">
                  Compute Information
                </Typography>
              </Box>

              <Box sx={{ pl: 3 }}>
                <DetailRow
                  label="Cluster ID"
                  value={task.cluster_id || 'Not assigned'}
                  monospace
                />

                {task.attempt_number !== undefined && (
                  <DetailRow
                    label="Attempt Number"
                    value={
                      <Chip
                        label={`Attempt ${task.attempt_number}`}
                        size="small"
                        color={task.attempt_number > 1 ? 'warning' : 'default'}
                        variant="outlined"
                        sx={{ fontSize: '0.7rem' }}
                      />
                    }
                  />
                )}
              </Box>
            </Box>

            {/* Task Type Information */}
            {(task.notebook_path || task.python_file || task.spark_jar_task || task.sql_task) && (
              <>
                <Divider sx={{ my: 2 }} />
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1.5 }}>
                    Task Configuration
                  </Typography>

                  {task.notebook_path && (
                    <DetailRow label="Notebook Path" value={task.notebook_path} monospace />
                  )}

                  {task.python_file && (
                    <DetailRow label="Python File" value={task.python_file} monospace />
                  )}

                  {task.spark_jar_task && (
                    <>
                      <DetailRow
                        label="Main Class"
                        value={task.spark_jar_task.main_class_name}
                        monospace
                      />
                      <DetailRow
                        label="JAR URI"
                        value={task.spark_jar_task.jar_uri}
                        monospace
                      />
                    </>
                  )}

                  {task.sql_task && (
                    <>
                      <DetailRow
                        label="Query ID"
                        value={task.sql_task.query_id}
                        monospace
                      />
                      <DetailRow
                        label="Warehouse ID"
                        value={task.sql_task.warehouse_id}
                        monospace
                      />
                    </>
                  )}
                </Box>
              </>
            )}

            {/* Dependencies */}
            {showDependencies && task.depends_on && task.depends_on.length > 0 && (
              <>
                <Divider sx={{ my: 2 }} />
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 1 }}>
                    Dependencies ({task.depends_on.length})
                  </Typography>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                    {task.depends_on.map(dep => (
                      <Chip
                        key={dep}
                        label={dep}
                        size="small"
                        variant="outlined"
                        onClick={onDependencyClick ? () => onDependencyClick(dep) : undefined}
                        sx={{
                          fontSize: '0.7rem',
                          cursor: onDependencyClick ? 'pointer' : 'default',
                          '&:hover': onDependencyClick
                            ? { bgcolor: 'action.hover' }
                            : undefined,
                        }}
                      />
                    ))}
                  </Box>
                </Box>
              </>
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
                      bgcolor: 'rgba(244, 67, 54, 0.1)',
                      borderColor: 'error.main',
                      maxHeight: 200,
                      overflow: 'auto',
                    }}
                  >
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: 'monospace',
                        fontSize: '0.75rem',
                        color: 'error.light',
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

export default TaskDetails;
