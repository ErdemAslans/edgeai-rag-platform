/**
 * Collaborator Presence Component
 * 
 * Shows real-time presence of collaborators on a document.
 */

import React, { useEffect, useState, useCallback } from 'react';
import { getCollaborators, sendHeartbeat, startSession, endSession, Collaborator, SessionResponse } from '../../api/collaboration';

interface CollaboratorPresenceProps {
  documentId: string;
  onCollaboratorsChange?: (collaborators: Collaborator[]) => void;
}

// Color palette for collaborator avatars
const AVATAR_COLORS = [
  'bg-red-500',
  'bg-blue-500',
  'bg-green-500',
  'bg-yellow-500',
  'bg-purple-500',
  'bg-pink-500',
  'bg-indigo-500',
  'bg-orange-500',
];

const getAvatarColor = (userId: string): string => {
  // Generate consistent color based on user ID
  let hash = 0;
  for (let i = 0; i < userId.length; i++) {
    hash = userId.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
};

const getInitials = (name: string): string => {
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
};

const CollaboratorPresence: React.FC<CollaboratorPresenceProps> = ({
  documentId,
  onCollaboratorsChange,
}) => {
  const [collaborators, setCollaborators] = useState<Collaborator[]>([]);
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Start session on mount
  useEffect(() => {
    const initSession = async () => {
      try {
        const clientId = `client_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        const sessionResponse = await startSession(documentId, clientId, {
          userAgent: navigator.userAgent,
          timestamp: new Date().toISOString(),
        });
        setSession(sessionResponse);
      } catch (error) {
        console.error('Failed to start collaboration session:', error);
      }
    };

    initSession();

    // Cleanup: end session on unmount
    return () => {
      if (session) {
        endSession(session.session_id).catch(console.error);
      }
    };
  }, [documentId]);

  // Fetch collaborators periodically
  const fetchCollaborators = useCallback(async () => {
    try {
      const result = await getCollaborators(documentId);
      setCollaborators(result.collaborators);
      onCollaboratorsChange?.(result.collaborators);
    } catch (error) {
      console.error('Failed to fetch collaborators:', error);
    } finally {
      setIsLoading(false);
    }
  }, [documentId, onCollaboratorsChange]);

  useEffect(() => {
    fetchCollaborators();
    
    // Poll for collaborators every 5 seconds
    const interval = setInterval(fetchCollaborators, 5000);
    
    return () => clearInterval(interval);
  }, [fetchCollaborators]);

  // Send heartbeat periodically
  useEffect(() => {
    if (!session) return;

    const sendPing = async () => {
      try {
        await sendHeartbeat(session.session_id);
      } catch (error) {
        console.error('Failed to send heartbeat:', error);
      }
    };

    // Send heartbeat every 10 seconds
    const interval = setInterval(sendPing, 10000);
    
    return () => clearInterval(interval);
  }, [session]);

  if (isLoading) {
    return (
      <div className="flex items-center space-x-1">
        <div className="w-8 h-8 rounded-full bg-gray-200 animate-pulse" />
      </div>
    );
  }

  if (collaborators.length === 0) {
    return null;
  }

  const displayedCollaborators = collaborators.slice(0, 5);
  const remainingCount = collaborators.length - 5;

  return (
    <div className="flex items-center">
      {/* Collaborator avatars */}
      <div className="flex -space-x-2">
        {displayedCollaborators.map((collaborator) => (
          <div
            key={collaborator.session_id}
            className={`relative inline-flex items-center justify-center w-8 h-8 rounded-full text-white text-xs font-medium ring-2 ring-white ${getAvatarColor(collaborator.user_id)}`}
            title={collaborator.user_name}
          >
            {getInitials(collaborator.user_name)}
            {/* Online indicator */}
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-green-400 border-2 border-white rounded-full" />
          </div>
        ))}
        
        {/* Overflow indicator */}
        {remainingCount > 0 && (
          <div className="relative inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-300 text-gray-600 text-xs font-medium ring-2 ring-white">
            +{remainingCount}
          </div>
        )}
      </div>

      {/* Collaborator count text */}
      <span className="ml-3 text-sm text-gray-600">
        {collaborators.length === 1
          ? '1 person viewing'
          : `${collaborators.length} people viewing`}
      </span>
    </div>
  );
};

export default CollaboratorPresence;