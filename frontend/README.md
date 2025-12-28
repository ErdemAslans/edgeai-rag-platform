# EdgeAI RAG Platform - Frontend

A clean, professional React frontend for the EdgeAI Multi-Agent RAG Platform.

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Tailwind CSS** - Styling (custom design system)
- **React Router v6** - Routing
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management
- **React Hook Form + Zod** - Form validation
- **Axios** - HTTP client
- **Lucide React** - Icons

## Design Philosophy

This frontend follows a "Swiss Banking meets Notion" design aesthetic:
- Clean, minimal, professional interface
- No AI/tech clichés (no neon colors, circuit patterns, etc.)
- Warm orange accent color (#e85d04) for trust and energy
- Inter font family for readability
- Subtle shadows and transitions

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn or pnpm

### Installation

```bash
# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Update the API URL if needed
# Edit .env and set VITE_API_URL to your backend URL
```

### Development

```bash
# Start development server
npm run dev

# The app will be available at http://localhost:3000
```

### Build for Production

```bash
# Build the application
npm run build

# Preview the production build
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── api/              # API client & endpoints
│   ├── components/
│   │   ├── ui/           # Base reusable components
│   │   ├── layout/       # Layout components
│   │   ├── documents/     # Document-related components
│   │   ├── chat/          # Chat interface components
│   │   └── agents/        # Agent-related components
│   ├── hooks/             # Custom React hooks
│   ├── pages/             # Page components
│   ├── stores/            # Zustand stores
│   ├── lib/               # Utilities and constants
│   ├── types/             # TypeScript type definitions
│   ├── App.tsx            # Main app component with routing
│   ├── main.tsx           # Application entry point
│   └── index.css          # Global styles
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── vite.config.ts
```

## Features

### Authentication
- Login and registration pages
- Protected routes with authentication check
- Token-based authentication with automatic refresh

### Dashboard
- Welcome message with user name
- Stats cards (Total Documents, Queries Today, Active Agents, Avg Response Time)
- Recent activity feed
- Quick action buttons

### Documents
- Document upload with drag & drop
- File type validation (PDF, TXT, CSV, Excel)
- Document grid with status indicators
- Search and filter functionality
- Document detail modal
- Delete documents

### Chat Interface
- Two-column layout (history + conversation)
- Message bubbles with user/assistant distinction
- Source references with collapsible details
- Agent selector dropdown
- Auto-expanding textarea input
- Keyboard shortcuts (Enter to send)

### Agents
- Agent cards with status indicators
- Agent descriptions
- Execution logs table
- Filter logs by agent

### Settings
- Profile information management
- Notification preferences
- Security settings section

## API Integration

All API calls are made through the `/src/api` directory:
- `client.ts` - Axios instance with interceptors
- `auth.ts` - Authentication endpoints
- `documents.ts` - Document management
- `queries.ts` - Query and chat endpoints
- `agents.ts` - Agent management

## State Management

- **authStore** - User authentication state
- **chatStore** - Chat conversation state

Both stores use Zustand with persistence.

## Custom Hooks

- `useAuth` - Authentication logic
- `useDocuments` - Document operations
- `useChat` - Chat functionality
- `useAgents` - Agent management

## Responsive Design

The application is fully responsive:
- Desktop (1440px+): Full layout with sidebar
- Tablet (768px-1439px): Collapsible sidebar
- Mobile (<768px): Bottom navigation or hamburger menu

## Environment Variables

Create a `.env` file in the root directory:

```env
VITE_API_URL=http://localhost:8000/api/v1
```

## Color Palette

- Primary: #1a1a1a (Almost black)
- Secondary: #fafafa (Off-white)
- Accent: #e85d04 (Warm orange)
- Success: #2d6a4f
- Error: #9d0208
- Border: #e5e5e5
- Text Primary: #171717
- Text Secondary: #737373

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## License

MIT
