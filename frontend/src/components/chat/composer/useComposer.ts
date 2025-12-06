import { useState, useRef, useCallback, useEffect } from 'react';
import { toast } from 'sonner';

export interface ComposerState {
  input: string;
  setInput: (value: string) => void;
  images: string[];
  isDragging: boolean;
  isListening: boolean;
  handleSend: () => void;
  handleImageUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  processFiles: (files: FileList | File[]) => void;
  removeImage: (index: number) => void;
  toggleVoiceInput: () => void;
  textareaRef: React.RefObject<HTMLTextAreaElement | null>;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
}

interface UseComposerProps {
  onSend: (content: string, images: string[]) => void;
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
  const [images, setImages] = useState<string[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isListening, setIsListening] = useState(false);
  
  // We cast to expected types, but initialize with null.
  // React.useRef requires the initial value to match the generic or null.
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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
    if ((!input.trim() && images.length === 0) || isStreaming) return;
    onSend(input, images);
    setInput('');
    setImages([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }, [input, images, isStreaming, onSend]);

  const processFiles = useCallback((files: FileList | File[]) => {
    const validFiles: File[] = [];
    Array.from(files).forEach(file => {
      if (file.size > 10 * 1024 * 1024) {
        toast.error(`File ${file.name} exceeds 10MB limit`);
        return;
      }
      if (!file.type.startsWith('image/')) {
        toast.error(`File ${file.name} is not an image`);
        return;
      }
      validFiles.push(file);
    });

    if (images.length + validFiles.length > 4) {
      toast.error('Max 4 images allowed');
      return;
    }

    validFiles.forEach(file => {
      const reader = new FileReader();
      reader.onloadend = () => {
        if (reader.result && typeof reader.result === 'string') {
          setImages(prev => [...prev, reader.result as string].slice(0, 4));
        }
      };
      reader.readAsDataURL(file);
    });
  }, [images]);

  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      processFiles(e.target.files);
    }
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, [processFiles]);

  const removeImage = useCallback((index: number) => {
    setImages(prev => prev.filter((_, i) => i !== index));
  }, []);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files) {
      processFiles(e.dataTransfer.files);
    }
  }, [processFiles]);

  return {
    input,
    setInput,
    images,
    isDragging,
    isListening,
    handleSend,
    handleImageUpload,
    processFiles,
    removeImage,
    toggleVoiceInput,
    textareaRef,
    fileInputRef,
    onDragOver,
    onDragLeave,
    onDrop
  };
}