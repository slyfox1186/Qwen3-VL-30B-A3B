import React, { useRef, useState } from 'react';
import { motion, useMotionValue, useSpring, useTransform, AnimatePresence } from 'framer-motion';
import { 
  ImagePlus, Sparkles, Code, FileText, BrainCircuit, 
  ChevronLeft, Terminal, Database, Globe, Palette, 
  PenTool, Search, FileJson
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface SuggestionNode {
  id: string;
  title: string;
  description: string;
  icon: React.ElementType;
  category: 'creative' | 'analysis' | 'coding' | 'general';
  prompt?: string;
  children?: SuggestionNode[];
}

const SUGGESTION_HIERARCHY: SuggestionNode[] = [
  {
    id: 'coding',
    title: 'Coding',
    description: 'Development & Engineering',
    icon: Code,
    category: 'coding',
    children: [
      {
        id: 'web',
        title: 'Web Development',
        description: 'React, Next.js, CSS',
        icon: Globe,
        category: 'coding',
        children: [
          { id: 'react-comp', title: 'New Component', description: 'Create a React component', icon: Code, category: 'coding', prompt: 'Create a modern, responsive React component for ' },
          { id: 'hook', title: 'Custom Hook', description: 'Logic extraction', icon: BrainCircuit, category: 'coding', prompt: 'Write a custom React hook that handles ' },
          { id: 'css', title: 'Tailwind Style', description: 'Styling assistance', icon: Palette, category: 'coding', prompt: 'Generate Tailwind CSS classes for ' },
        ]
      },
      {
        id: 'backend',
        title: 'Backend & API',
        description: 'Python, Node, DB',
        icon: Terminal,
        category: 'coding',
        children: [
          { id: 'py-script', title: 'Python Script', description: 'Automation & logic', icon: FileJson, category: 'coding', prompt: 'Write a Python script to ' },
          { id: 'api-route', title: 'API Endpoint', description: 'REST/GraphQL', icon: Globe, category: 'coding', prompt: 'Create an API endpoint that ' },
          { id: 'sql', title: 'SQL Query', description: 'Database operations', icon: Database, category: 'coding', prompt: 'Write an optimized SQL query to ' },
        ]
      },
      {
        id: 'debug',
        title: 'Debugging',
        description: 'Fix errors & optimize',
        icon: Search,
        category: 'coding',
        children: [
          { id: 'fix-error', title: 'Fix Error', description: 'Analyze stack trace', icon: BrainCircuit, category: 'coding', prompt: 'Help me fix this error: ' },
          { id: 'optimize', title: 'Optimize', description: 'Improve performance', icon: Sparkles, category: 'coding', prompt: 'Optimize this code for better performance: ' },
        ]
      }
    ]
  },
  {
    id: 'analysis',
    title: 'Analysis',
    description: 'Understand & Extract',
    icon: BrainCircuit,
    category: 'analysis',
    children: [
      {
        id: 'visual',
        title: 'Visual Analysis',
        description: 'Images & Diagrams',
        icon: ImagePlus,
        category: 'analysis',
        children: [
          { id: 'desc-img', title: 'Describe', description: 'Detailed breakdown', icon: FileText, category: 'analysis', prompt: 'Provide a detailed description of this image, focusing on ' },
          { id: 'extract-text', title: 'Extract Text', description: 'OCR & Transcription', icon: FileText, category: 'analysis', prompt: 'Transcribe all text visible in this image.' },
        ]
      },
      {
        id: 'text-analysis',
        title: 'Text Analysis',
        description: 'Summarize & Review',
        icon: FileText,
        category: 'analysis',
        children: [
          { id: 'summarize', title: 'Summarize', description: 'Key points only', icon: FileText, category: 'analysis', prompt: 'Summarize the following text into bullet points: ' },
          { id: 'sentiment', title: 'Sentiment', description: 'Tone & emotion', icon: BrainCircuit, category: 'analysis', prompt: 'Analyze the sentiment and tone of this text: ' },
        ]
      }
    ]
  },
  {
    id: 'creative',
    title: 'Creative',
    description: 'Write, Design, Ideate',
    icon: Sparkles,
    category: 'creative',
    children: [
      {
        id: 'writing',
        title: 'Writing',
        description: 'Stories, Copy, Blog',
        icon: PenTool,
        category: 'creative',
        children: [
          { id: 'story', title: 'Short Story', description: 'Fiction & Narrative', icon: FileText, category: 'creative', prompt: 'Write a short story about ' },
          { id: 'blog', title: 'Blog Post', description: 'Content marketing', icon: Globe, category: 'creative', prompt: 'Write an engaging blog post about ' },
        ]
      },
      {
        id: 'design',
        title: 'Design Ideas',
        description: 'UI, Art, Concepts',
        icon: Palette,
        category: 'creative',
        children: [
          { id: 'ui-concept', title: 'UI Concept', description: 'Interface ideas', icon: Globe, category: 'creative', prompt: 'Describe a modern UI design for ' },
          { id: 'art-prompt', title: 'Art Prompt', description: 'Generative art', icon: ImagePlus, category: 'creative', prompt: 'Create a detailed prompt for an AI image generator describing ' },
        ]
      }
    ]
  }
];

interface PromptDeckProps {
  onSelect: (text: string) => void;
  isVisible: boolean;
}

export function PromptDeck({ onSelect, isVisible }: PromptDeckProps) {
  const [history, setHistory] = useState<SuggestionNode[]>([]);
  const currentLevel = history.length > 0 
    ? history[history.length - 1].children || [] 
    : SUGGESTION_HIERARCHY;

  const handleCardClick = (node: SuggestionNode) => {
    if (node.children) {
      setHistory([...history, node]);
    } else if (node.prompt) {
      onSelect(node.prompt);
    }
  };

  const handleBack = () => {
    setHistory(history.slice(0, -1));
  };

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ 
        height: isVisible ? 'auto' : 0, 
        opacity: isVisible ? 1 : 0 
      }}
      exit={{ height: 0, opacity: 0 }}
      className="relative w-full mb-4"
    >
      <div className="relative w-full flex gap-3 p-4 pb-8 overflow-x-auto scrollbar-none mask-linear-fade items-center justify-center min-h-[140px]">
        <AnimatePresence mode="wait" initial={false}>
          {history.length > 0 ? (
            <motion.div
              key="level-sub"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.2 }}
              className="flex gap-3 items-center justify-center min-w-0"
            >
              <motion.button
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                onClick={handleBack}
                className="shrink-0 h-24 flex items-center justify-center px-4 rounded-xl border border-border/50 bg-background/50 backdrop-blur-sm hover:bg-background/80 transition-colors group mr-2"
              >
                <div className="flex flex-col items-center gap-2 w-max">
                  <div className="p-2 rounded-full bg-muted group-hover:bg-primary/10 transition-colors">
                    <ChevronLeft className="w-5 h-5 text-muted-foreground group-hover:text-primary" />
                  </div>
                  <span className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">Back</span>
                </div>
              </motion.button>
              
              {currentLevel.map((card) => (
                <PromptCardWrapper key={card.id} card={card} onClick={() => handleCardClick(card)} />
              ))}
            </motion.div>
          ) : (
            <motion.div
              key="level-root"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.2 }}
              className="flex gap-3 items-center justify-center min-w-0"
            >
              {currentLevel.map((card) => (
                <PromptCardWrapper key={card.id} card={card} onClick={() => handleCardClick(card)} />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.div>
  );
}

function PromptCardWrapper({ card, onClick }: { card: SuggestionNode, onClick: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
    >
      <PromptCard3D card={card} onClick={onClick} />
    </motion.div>
  );
}

function PromptCard3D({ card, onClick }: { card: SuggestionNode, onClick: () => void }) {
  const ref = useRef<HTMLButtonElement>(null);

  // 3D Tilt Effect Logic
  const x = useMotionValue(0);
  const y = useMotionValue(0);

  const mouseX = useSpring(x, { stiffness: 500, damping: 100 });
  const mouseY = useSpring(y, { stiffness: 500, damping: 100 });

  const rotateX = useTransform(mouseY, [-0.5, 0.5], ["12deg", "-12deg"]);
  const rotateY = useTransform(mouseX, [-0.5, 0.5], ["-12deg", "12deg"]);

  const handleMouseMove = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (!ref.current) return;

    const rect = ref.current.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    const mouseXFromCenter = e.clientX - rect.left - width / 2;
    const mouseYFromCenter = e.clientY - rect.top - height / 2;

    x.set(mouseXFromCenter / width);
    y.set(mouseYFromCenter / height);
  };

  const handleMouseLeave = () => {
    x.set(0);
    y.set(0);
  };

  const getGradient = (category: string) => {
    switch (category) {
      case 'coding': return 'from-blue-500/20 via-cyan-400/10 to-transparent';
      case 'creative': return 'from-purple-500/20 via-pink-400/10 to-transparent';
      case 'analysis': return 'from-emerald-500/20 via-green-400/10 to-transparent';
      default: return 'from-primary/20 via-primary/10 to-transparent';
    }
  };

  return (
    <motion.button
      ref={ref}
      style={{
        rotateX,
        rotateY,
        perspective: '1000px',
        transformStyle: "preserve-3d",
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={onClick}
      className={cn(
        "prompt-card-base group"
      )}
    >
      {/* Inner Glare */}
      <div 
        className={cn(
          "prompt-card-glare",
          getGradient(card.category)
        )} 
      />
      
      <div 
        className="prompt-card-content"
        style={{ transform: 'translateZ(25px)' }}
      >
        <card.icon className={cn(
          "w-5 h-5 transition-colors duration-300",
          card.category === 'coding' ? 'text-blue-500' : 
          card.category === 'creative' ? 'text-purple-500' : 'text-emerald-500'
        )} />
        
        <div>
          <h3 className="text-xs font-semibold text-foreground/90 group-hover:text-foreground transition-colors">
            {card.title}
          </h3>
          <p className="text-[10px] text-muted-foreground group-hover:text-muted-foreground/80">
            {card.description}
          </p>
        </div>
      </div>
    </motion.button>
  );
}
