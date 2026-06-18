# Ollama Arena v2.5.0 - Frontend Migration Guide

## Overview

Ollama Arena v2.5.0 introduces a modern React-based frontend with enterprise features, replacing the previous FastAPI + Jinja2 + GSAP architecture. This guide covers the migration, new features, and deployment options.

## What's New in v2.5.0

### 1. Modern React Frontend
- **Technology Stack**: React 18 + Vite + TypeScript + Tailwind CSS
- **State Management**: Zustand for efficient state management
- **Data Fetching**: React Query (@tanstack/react-query) for server state
- **3D Visualization**: @react-three/fiber for interactive 3D visualizations
- **Performance**: Code splitting, lazy loading, and optimized bundle sizes

### 2. Community Leaderboard
- **Public GitHub Pages**: Static leaderboard page deployable to GitHub Pages
- **Real-time Updates**: Fetches data from backend API
- **Responsive Design**: Works on all screen sizes
- **Visual Charts**: Plotly integration for performance visualizations

### 3. Enterprise Features
- **SSO Integration**: OAuth2/OIDC support for Google, GitHub, and custom providers
- **Advanced Security**: Configurable CSP, rate limiting, and authentication requirements
- **Security UI**: Settings page for configuring security options
- **CORS Configuration**: Easy-to-use CORS settings interface

## Migration Guide

### Option 1: Continue Using Jinja2 Templates (Default)

The existing Jinja2 template system remains fully functional. No changes required:

```bash
ollama-arena web
```

### Option 2: Use New React Frontend

To use the new React frontend, you need to build it first:

```bash
# Install frontend dependencies
cd frontend
npm install

# Build the React app
npm run build

# Run the web server with React frontend
cd ..
ollama-arena web --react
```

### Option 3: Development Mode

For development with hot-reload:

```bash
cd frontend
npm install
npm run dev
```

This runs the React dev server on port 3000 with API proxy to the backend.

## Frontend Development

### Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable React components
│   │   ├── Layout.tsx      # Main layout with navigation
│   │   ├── StatCard.tsx    # Statistics cards
│   │   ├── RecentMatches.tsx
│   │   ├── QuickActions.tsx
│   │   ├── Arena3D.tsx      # 3D visualization wrapper
│   │   └── Arena3DScene.tsx # Three.js scene
│   ├── pages/              # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Leaderboard.tsx
│   │   ├── Battle.tsx
│   │   ├── Tournament.tsx
│   │   ├── Playground.tsx
│   │   ├── Genome.tsx
│   │   └── Settings.tsx
│   ├── lib/                # Utilities and API client
│   │   ├── api.ts          # API client with typed responses
│   │   └── utils.ts        # Utility functions
│   ├── store/              # State management
│   │   └── useArenaStore.ts
│   ├── App.tsx             # Main app component
│   ├── main.tsx            # Entry point
│   └── index.css           # Global styles with Tailwind
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.js
└── index.html
```

### Adding New Components

1. Create component in `src/components/`
2. Use TypeScript for type safety
3. Follow accessibility best practices (ARIA labels, semantic HTML)
4. Use Tailwind CSS for styling

### API Integration

The API client is located in `src/lib/api.ts`:

```typescript
import { api } from '@/lib/api'

// Fetch leaderboard
const { data: leaderboard } = useQuery({
  queryKey: ['leaderboard'],
  queryFn: api.getLeaderboard,
})

// Create a match
const jobId = await api.createMatch({
  models: ['model-a', 'model-b'],
  category: 'coding',
  n: 10,
})
```

## Enterprise Features

### SSO Configuration

1. Navigate to Settings page in the web UI
2. Select your SSO provider (Google, GitHub, or OpenID Connect)
3. Enter your OAuth client ID and secret
4. Enable SSO authentication

### Security Settings

Configure security options via the Settings page:

- **Content Security Policy (CSP)**: Enable/disable CSP headers
- **Rate Limiting**: Configure request rate limits per IP
- **Authentication**: Require authentication for API access
- **CORS**: Configure allowed origins for cross-origin requests

## Public Leaderboard

### Deployment to GitHub Pages

The public leaderboard is automatically deployed via GitHub Actions when changes are pushed to the `public-leaderboard/` directory.

To deploy:

1. Enable GitHub Pages in your repository settings
2. Set source to "GitHub Actions"
3. Push changes to the main branch
4. The workflow will automatically deploy to GitHub Pages

### Customization

Edit `public-leaderboard/index.html` to customize:
- Branding and styling
- Chart configurations
- Data sources (currently uses mock data, connect to real API in production)

## Performance Optimizations

### Code Splitting

The Vite configuration includes automatic code splitting:

```typescript
// vite.config.ts
rollupOptions: {
  output: {
    manualChunks: {
      'react-vendor': ['react', 'react-dom', 'react-router-dom'],
      'ui-vendor': ['zustand', '@tanstack/react-query'],
      'viz-vendor': ['plotly.js-dist-min', 'react-plotly.js'],
      'three-vendor': ['three', '@react-three/fiber', '@react-three/drei'],
    },
  },
}
```

### Lazy Loading

Heavy components are lazy-loaded:

```typescript
const Arena3DScene = lazy(() => import('./Arena3DScene'))
```

## Accessibility

The new frontend includes accessibility features:

- Semantic HTML elements
- ARIA labels and roles
- Keyboard navigation support
- Screen reader compatibility
- High contrast color ratios
- Focus indicators

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## Troubleshooting

### Build Fails

```bash
# Clear node_modules and reinstall
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

### API Connection Issues

Check that the backend is running and accessible:

```bash
# Check backend is running
curl http://localhost:7860/api/leaderboard
```

### 3D Visualization Not Loading

Ensure WebGL is enabled in your browser. The 3D visualization requires:

- WebGL support
- Hardware acceleration
- Sufficient GPU memory

## Contributing

When contributing to the frontend:

1. Follow TypeScript best practices
2. Use ESLint for code quality
3. Test on multiple browsers
4. Ensure accessibility compliance
5. Write tests for new components

## Future Roadmap

- [ ] Real-time WebSocket updates for live matches
- [ ] Advanced analytics and filtering
- [ ] Export to PDF/CSV functionality
- [ ] Dark/light theme toggle
- [ ] Internationalization (i18n)
- [ ] Mobile app (React Native)
- [ ] PWA support for offline usage

## Support

For issues or questions:

- GitHub Issues: https://github.com/nazkari86-lab/ollama-arena/issues
- Documentation: https://github.com/nazkari86-lab/ollama-arena#readme
- Contributing Guide: CONTRIBUTING.md
