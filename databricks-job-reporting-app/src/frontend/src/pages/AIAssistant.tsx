import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Box,
  Paper,
  Typography,
  TextField,
  IconButton,
  Avatar,
  Chip,
  CircularProgress,
  Card,
  CardContent,
  Divider,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Alert,
  Tooltip,
} from '@mui/material';
import {
  Send as SendIcon,
  SmartToy as BotIcon,
  Person as UserIcon,
  Refresh as RefreshIcon,
  AutoAwesome as SparkleIcon,
  Psychology as GenieIcon,
} from '@mui/icons-material';
import ReactMarkdown from 'react-markdown';
import {
  startGenieConversation,
  sendGenieMessage,
  getGenieSpaces,
} from '../services/api';
import type { ChatMessage } from '../types';

const suggestedQuestions = [
  'What are the top 5 most expensive jobs in the last 30 days?',
  'Show me all failed jobs from yesterday',
  'Which jobs have the longest average runtime?',
  'What is the success rate by job type?',
  'List jobs that have been running for more than 2 hours',
  'What is the total cost trend over the past week?',
  'Show me jobs with high retry rates',
  'Which users have the most job runs?',
];

const AIAssistant: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [spaces, setSpaces] = useState<any[]>([]);
  const [selectedSpace, setSelectedSpace] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchSpaces = async () => {
      try {
        const spacesData = await getGenieSpaces();
        setSpaces(spacesData);
        if (spacesData.length > 0) {
          setSelectedSpace(spacesData[0].id);
        }
      } catch (err) {
        console.error('Failed to fetch Genie spaces:', err);
        setError('Failed to load Genie Spaces. Please configure a Genie Space in settings.');
      }
    };
    fetchSpaces();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startNewConversation = async () => {
    if (!selectedSpace) {
      setError('Please select a Genie Space first');
      return;
    }
    try {
      setLoading(true);
      const convId = await startGenieConversation(selectedSpace);
      setConversationId(convId);
      setMessages([]);
      setError(null);
    } catch (err) {
      console.error('Failed to start conversation:', err);
      setError('Failed to start conversation. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    if (!input.trim() || loading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    // Add loading message
    const loadingId = (Date.now() + 1).toString();
    setMessages((prev) => [
      ...prev,
      {
        id: loadingId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
        isLoading: true,
      },
    ]);

    try {
      let convId = conversationId;
      if (!convId) {
        convId = await startGenieConversation(selectedSpace);
        setConversationId(convId);
      }

      const response = await sendGenieMessage(selectedSpace, convId, userMessage.content);

      // Replace loading message with actual response
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === loadingId
            ? {
                ...msg,
                content: response,
                isLoading: false,
              }
            : msg
        )
      );
      setError(null);
    } catch (err) {
      console.error('Failed to send message:', err);
      // Remove loading message and show error
      setMessages((prev) => prev.filter((msg) => msg.id !== loadingId));
      setError('Failed to get response. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleSuggestionClick = (question: string) => {
    setInput(question);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <Box sx={{ height: 'calc(100vh - 140px)', display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <Box sx={{ mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2 }}>
          <GenieIcon sx={{ fontSize: 40, color: 'primary.main' }} />
          <Box>
            <Typography variant="h4" fontWeight="bold">
              AI Assistant
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Powered by Databricks Genie Spaces - Ask questions about your jobs in natural language
            </Typography>
          </Box>
        </Box>

        <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
          <FormControl size="small" sx={{ minWidth: 300 }}>
            <InputLabel>Genie Space</InputLabel>
            <Select
              value={selectedSpace}
              label="Genie Space"
              onChange={(e) => setSelectedSpace(e.target.value)}
            >
              {spaces.map((space) => (
                <MenuItem key={space.id} value={space.id}>
                  {space.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          <Tooltip title="Start New Conversation">
            <IconButton onClick={startNewConversation} color="primary">
              <RefreshIcon />
            </IconButton>
          </Tooltip>
          {conversationId && (
            <Chip
              label={`Conversation: ${conversationId.slice(0, 8)}...`}
              size="small"
              color="success"
            />
          )}
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Chat Area */}
      <Paper
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          borderRadius: 3,
          overflow: 'hidden',
          bgcolor: 'background.paper',
        }}
      >
        {/* Messages */}
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            p: 3,
            display: 'flex',
            flexDirection: 'column',
            gap: 2,
          }}
        >
          {messages.length === 0 ? (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <SparkleIcon sx={{ fontSize: 60, color: 'primary.main', mb: 2 }} />
              <Typography variant="h6" gutterBottom>
                Start a conversation
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                Ask questions about your Databricks jobs, costs, and performance
              </Typography>
              <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 2 }}>
                Try asking:
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, justifyContent: 'center' }}>
                {suggestedQuestions.slice(0, 4).map((question, index) => (
                  <motion.div
                    key={index}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                  >
                    <Chip
                      label={question}
                      onClick={() => handleSuggestionClick(question)}
                      sx={{
                        cursor: 'pointer',
                        '&:hover': { bgcolor: 'primary.main', color: 'white' },
                      }}
                    />
                  </motion.div>
                ))}
              </Box>
            </Box>
          ) : (
            <AnimatePresence>
              {messages.map((message) => (
                <motion.div
                  key={message.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  transition={{ duration: 0.3 }}
                >
                  <Box
                    sx={{
                      display: 'flex',
                      gap: 2,
                      flexDirection: message.role === 'user' ? 'row-reverse' : 'row',
                    }}
                  >
                    <Avatar
                      sx={{
                        bgcolor: message.role === 'user' ? 'primary.main' : 'secondary.main',
                        width: 36,
                        height: 36,
                      }}
                    >
                      {message.role === 'user' ? <UserIcon /> : <BotIcon />}
                    </Avatar>
                    <Card
                      sx={{
                        maxWidth: '70%',
                        bgcolor:
                          message.role === 'user'
                            ? 'primary.main'
                            : 'background.default',
                        color: message.role === 'user' ? 'white' : 'text.primary',
                      }}
                    >
                      <CardContent sx={{ py: 1.5, px: 2, '&:last-child': { pb: 1.5 } }}>
                        {message.isLoading ? (
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <CircularProgress size={16} />
                            <Typography variant="body2">Thinking...</Typography>
                          </Box>
                        ) : (
                          <Box
                            sx={{
                              '& p': { m: 0 },
                              '& pre': {
                                bgcolor: 'rgba(0,0,0,0.2)',
                                p: 1,
                                borderRadius: 1,
                                overflow: 'auto',
                              },
                              '& code': {
                                bgcolor: 'rgba(0,0,0,0.2)',
                                px: 0.5,
                                borderRadius: 0.5,
                                fontFamily: 'monospace',
                              },
                              '& table': {
                                borderCollapse: 'collapse',
                                width: '100%',
                                my: 1,
                              },
                              '& th, & td': {
                                border: '1px solid',
                                borderColor: 'divider',
                                p: 1,
                                textAlign: 'left',
                              },
                            }}
                          >
                            <ReactMarkdown>{message.content}</ReactMarkdown>
                          </Box>
                        )}
                      </CardContent>
                    </Card>
                  </Box>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
          <div ref={messagesEndRef} />
        </Box>

        <Divider />

        {/* Input Area */}
        <Box sx={{ p: 2, bgcolor: 'background.default' }}>
          <Box sx={{ display: 'flex', gap: 1 }}>
            <TextField
              fullWidth
              placeholder="Ask about your Databricks jobs..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              disabled={loading || !selectedSpace}
              multiline
              maxRows={4}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 3,
                },
              }}
            />
            <IconButton
              color="primary"
              onClick={handleSend}
              disabled={loading || !input.trim() || !selectedSpace}
              sx={{
                bgcolor: 'primary.main',
                color: 'white',
                '&:hover': { bgcolor: 'primary.dark' },
                '&:disabled': { bgcolor: 'action.disabled' },
              }}
            >
              <SendIcon />
            </IconButton>
          </Box>
          <Box sx={{ mt: 1, display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
            {suggestedQuestions.slice(4).map((question, index) => (
              <Chip
                key={index}
                label={question}
                size="small"
                variant="outlined"
                onClick={() => handleSuggestionClick(question)}
                sx={{ cursor: 'pointer', fontSize: '0.7rem' }}
              />
            ))}
          </Box>
        </Box>
      </Paper>
    </Box>
  );
};

export default AIAssistant;
