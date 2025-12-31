/**
 * Feedback buttons component for chat messages
 * Allows users to provide thumbs up/down feedback on responses
 */

import React, { useState } from 'react';
import { submitQuickFeedback } from '../../api/feedback';

interface FeedbackButtonsProps {
  queryId: string;
  onFeedbackSubmitted?: (isPositive: boolean) => void;
  className?: string;
}

type FeedbackState = 'none' | 'positive' | 'negative' | 'submitting';

export const FeedbackButtons: React.FC<FeedbackButtonsProps> = ({
  queryId,
  onFeedbackSubmitted,
  className = '',
}) => {
  const [feedbackState, setFeedbackState] = useState<FeedbackState>('none');
  const [error, setError] = useState<string | null>(null);

  const handleFeedback = async (isPositive: boolean) => {
    if (feedbackState === 'submitting' || feedbackState !== 'none') {
      return;
    }

    setFeedbackState('submitting');
    setError(null);

    try {
      await submitQuickFeedback({
        query_id: queryId,
        is_positive: isPositive,
      });

      setFeedbackState(isPositive ? 'positive' : 'negative');
      onFeedbackSubmitted?.(isPositive);
    } catch (err: unknown) {
      console.error('Failed to submit feedback:', err);
      setError('Geri bildirim gönderilemedi');
      setFeedbackState('none');
    }
  };

  const getButtonClass = (type: 'positive' | 'negative') => {
    const baseClass = 'p-2 rounded-full transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2';
    
    if (feedbackState === 'submitting') {
      return `${baseClass} opacity-50 cursor-not-allowed`;
    }

    if (feedbackState === type) {
      return type === 'positive'
        ? `${baseClass} bg-green-100 text-green-600 ring-2 ring-green-500`
        : `${baseClass} bg-red-100 text-red-600 ring-2 ring-red-500`;
    }

    if (feedbackState !== 'none') {
      return `${baseClass} opacity-30 cursor-not-allowed`;
    }

    return type === 'positive'
      ? `${baseClass} hover:bg-green-100 text-gray-400 hover:text-green-600 focus:ring-green-500`
      : `${baseClass} hover:bg-red-100 text-gray-400 hover:text-red-600 focus:ring-red-500`;
  };

  return (
    <div className={`flex items-center gap-1 ${className}`}>
      {/* Thumbs Up Button */}
      <button
        onClick={() => handleFeedback(true)}
        disabled={feedbackState !== 'none'}
        className={getButtonClass('positive')}
        title="Yararlı"
        aria-label="Bu yanıt yararlıydı"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5"
          fill={feedbackState === 'positive' ? 'currentColor' : 'none'}
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.263 21h-4.017c-.163 0-.326-.02-.485-.06L7 20m7-10V5a2 2 0 00-2-2h-.095c-.5 0-.905.405-.905.905 0 .714-.211 1.412-.608 2.006L7 11v9m7-10h-2M7 20H5a2 2 0 01-2-2v-6a2 2 0 012-2h2.5"
          />
        </svg>
      </button>

      {/* Thumbs Down Button */}
      <button
        onClick={() => handleFeedback(false)}
        disabled={feedbackState !== 'none'}
        className={getButtonClass('negative')}
        title="Yararlı değil"
        aria-label="Bu yanıt yararlı değildi"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-5 w-5"
          fill={feedbackState === 'negative' ? 'currentColor' : 'none'}
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10 14H5.236a2 2 0 01-1.789-2.894l3.5-7A2 2 0 018.737 3h4.018a2 2 0 01.485.06l3.76.94m-7 10v5a2 2 0 002 2h.096c.5 0 .905-.405.905-.904 0-.715.211-1.413.608-2.008L17 13V4m-7 10h2m5-10h2a2 2 0 012 2v6a2 2 0 01-2 2h-2.5"
          />
        </svg>
      </button>

      {/* Feedback confirmation */}
      {feedbackState === 'positive' && (
        <span className="text-xs text-green-600 ml-2">Teşekkürler!</span>
      )}
      {feedbackState === 'negative' && (
        <span className="text-xs text-red-600 ml-2">Geri bildiriminiz alındı</span>
      )}

      {/* Error message */}
      {error && (
        <span className="text-xs text-red-500 ml-2">{error}</span>
      )}
    </div>
  );
};

export default FeedbackButtons;