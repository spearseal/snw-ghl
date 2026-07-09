'use client';

import { Moon, Sun } from 'lucide-react';
import { useTheme } from '@/components/ThemeProvider';
import Button from '@/components/ui/Button';

interface ThemeToggleProps {
  className?: string;
  showLabel?: boolean;
}

export default function ThemeToggle({ className = '', showLabel = true }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === 'dark';

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleTheme}
      title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      className={className}
      leftIcon={isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    >
      {showLabel && (isDark ? 'Light mode' : 'Dark mode')}
    </Button>
  );
}
