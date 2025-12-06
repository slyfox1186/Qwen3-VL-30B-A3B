import { useState, useRef, useCallback, useEffect } from 'react';
import { toast } from 'sonner';

export interface ComposerState {
  input: string;
  setInput: (value: string) => void;
  isListening: boolean;
  handleSend: () => void;
  toggleVoiceInput: () => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
}

interface UseComposerProps {
  onSend: (content: string) => void;
  isStreaming: boolean;
}

// Speech Recognition Interfaces
interface SpeechRecognitionEvent extends Event {
  results: {
    [key: number]: {
      [key: number]: {
        transcript: string;
      };
    };
  } & Iterable<unknown>;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
  message: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: (event: Event) => void;
  onend: (event: Event) => void;
  onerror: (event: SpeechRecognitionErrorEvent) => void;
  onresult: (event: SpeechRecognitionEvent) => void;
}

export function useComposer({ onSend, isStreaming }: UseComposerProps): ComposerState {
  const [input, setInput] = useState('');
  const [isListening, setIsListening] = useState(false);

  // We cast to expected types, but initialize with null.
  // React.useRef requires the initial value to match the generic or null.
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [input]);

  // Initialize Speech Recognition
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const SpeechRecognitionConstructor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

      if (SpeechRecognitionConstructor) {
        const recognition = new SpeechRecognitionConstructor() as SpeechRecognition;
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => setIsListening(true);
        recognition.onend = () => setIsListening(false);
        recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
          console.error('Speech recognition error', event.error);
          setIsListening(false);
          toast.error('Voice input failed: ' + event.error);
        };
        recognition.onresult = (event: SpeechRecognitionEvent) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const result = (event.results as any)[0][0];
          const transcript = result.transcript;
          setInput(prev => (prev ? prev + ' ' + transcript : transcript));
        };

        recognitionRef.current = recognition;
      }
    }
  }, []);

  const toggleVoiceInput = useCallback(() => {
    if (!recognitionRef.current) {
      toast.error('Speech recognition not supported in this browser.');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
    } else {
      recognitionRef.current.start();
      toast.info('Listening...');
    }
  }, [isListening]);

  const handleSend = useCallback(() => {
    if (!input.trim() || isStreaming) return;
    onSend(input);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }, [input, isStreaming, onSend]);

  return {
    input,
    setInput,
    isListening,
    handleSend,
    toggleVoiceInput,
    textareaRef,
  };
}
