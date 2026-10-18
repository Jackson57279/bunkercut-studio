import React, { useEffect, useRef, useState } from 'react';
import {
  AlertCircle,
  AudioWaveform,
  BookOpen,
  Check,
  Clapperboard,
  Clock,
  Copy,
  Download,
  Eye,
  Film,
  FolderKanban,
  Gauge,
  Grid,
  Image as ImageIcon,
  LayoutList,
  Loader2,
  Mic,
  Pause,
  Play,
  Plus,
  RefreshCw,
  Settings,
  Sparkles,
  Subtitles,
  Trash2,
  Users,
  Video,
  Volume2,
  Wand2,
} from 'lucide-react';
import {
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Dialog,
  DialogContent,
  Input,
  Progress,
  Switch,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
} from './components/ui/primitives';
import type {
  CastMember,
  Project,
  ReferenceAnalysis,
  SceneItem,
  StudioStatus,
} from './types';

type NavSection = 'storyboard' | 'cast' | 'engine' | 'voicelab' | 'reference';
type StoryboardLayout = 'cards' | 'table';

function formatMinSec(sec: number): string {
  const s = Math.max(0, Math.round(sec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}m ${String(r).padStart(2, '0')}s`;
}

export default function App() {
  const [nav, setNav] = useState<NavSection>('storyboard');
  const [layoutMode, setLayoutMode] = useState<StoryboardLayout>('cards');

  const [status, setStatus] = useState<StudioStatus | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProject] = useState<Project | null>(null);
  const [refData, setRefData] = useState<ReferenceAnalysis | null>(null);

  const [loadingInit, setLoadingInit] = useState(true);
  const [busyBanner, setBusyBanner] = useState<string | null>(null);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);
  const [sceneBusy, setSceneBusy] = useState<Record<string, string>>({});

  // New Video Dialog state
  const [newDialogOpen, setNewDialogOpen] = useState(false);
  const [newPrompt, setNewPrompt] = useState('');
  const [newSceneCount, setNewSceneCount] = useState(64);
  const [newDensity, setNewDensity] = useState<'smart_2x' | 'smart_3x' | 'every_beat'>('smart_2x');
  const [newVoicePresetId, setNewVoicePresetId] = useState<string>('male_grant');
  const [newLlmModel, setNewLlmModel] = useState<string>('anthropic/claude-sonnet-5.5');

  // Cast creation state
  const [newCharName, setNewCharName] = useState('');
  const [newCharRole, setNewCharRole] = useState('');
  const [newCharBadge, setNewCharBadge] = useState('');
  const [newCharDesc, setNewCharDesc] = useState(
    'A 2D stick-figure character with thin uniform black stick limbs (#000000), a simple round white head, expressive cartoon eyes, wearing a dark navy captain hat, and simple white oval feet.'
  );
  const [creatingChar, setCreatingChar] = useState(false);
  const [regeneratingCastId, setRegeneratingCastId] = useState<string | null>(null);

  // Chapter filter & selected scene for inspector
  const [chapterFilter, setChapterFilter] = useState<string>('ALL');
  const [editingSceneId, setEditingSceneId] = useState<string | null>(null);

  // Settings modal (API key)
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [apiKeyInput, setApiKeyInput] = useState('');

  // Lightbox
  const [lightbox, setLightbox] = useState<{ url: string; title: string } | null>(null);

  // Audio / Video refs
  const [previewAudioUrl, setPreviewAudioUrl] = useState<string | null>(null);
  const [previewingVoice, setPreviewingVoice] = useState(false);
  const [voiceLabText, setVoiceLabText] = useState(
    "The sirens start at 6:14 a.m. Not the monthly test. You know the difference. These don't stop."
  );
  const audioPreviewEl = useRef<HTMLAudioElement | null>(null);
  const refVideoEl = useRef<HTMLVideoElement | null>(null);

  const [customYtUrl, setCustomYtUrl] = useState('');
  const [downloadingYt, setDownloadingYt] = useState(false);
  const [copiedChapters, setCopiedChapters] = useState(false);

  const fetchAll = async (selectId?: string) => {
    try {
      const [stRes, prRes, rfRes] = await Promise.all([
        fetch('/api/status'),
        fetch('/api/projects'),
        fetch('/api/reference'),
      ]);
      const stData = await stRes.json();
      const prData = await prRes.json();
      const rfData = await rfRes.json();

      setStatus(stData);
      const list: Project[] = prData.projects || [];
      setProjects(list);
      setRefData(rfData);

      if (list.length > 0) {
        const target =
          (selectId && list.find((p) => p.id === selectId)) ||
          (currentProject && list.find((p) => p.id === currentProject.id)) ||
          list[0];
        setCurrentProject(target);
      }
    } catch (err: any) {
      setErrorBanner(err.message || 'Failed to connect to studio server');
    } finally {
      setLoadingInit(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  // Poll active background job
  useEffect(() => {
    if (!currentProject?.active_job || currentProject.active_job.status !== 'running') {
      return;
    }
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/projects/${currentProject.id}`);
        if (res.ok) {
          const data = await res.json();
          setCurrentProject(data.project);
          setProjects((prev) =>
            prev.map((p) => (p.id === data.project.id ? data.project : p))
          );
          if (data.project.active_job?.status === 'error') {
            setErrorBanner(data.project.active_job.detail);
          }
        }
      } catch {
        // ignore transient error
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [currentProject?.id, currentProject?.active_job?.status]);

  const handleSelectProject = (proj: Project) => {
    setCurrentProject(proj);
    setChapterFilter('ALL');
    setNav('storyboard');
    setErrorBanner(null);
  };

  const handleLaunchFromPrompt = async (autoProduce: boolean) => {
    const promptText = newPrompt.trim();
    if (!promptText) {
      setErrorBanner('Please enter a video prompt.');
      return;
    }
    setErrorBanner(null);
    setNewDialogOpen(false);
    setBusyBanner(
      autoProduce
        ? `Initializing ${newSceneCount}-beat long-form production...`
        : `Architecting ${newSceneCount}-beat multi-chapter storyboard...`
    );

    try {
      const chosenVoice = status?.featured_voices?.find((fv) => fv.id === newVoicePresetId);
      const baseSettings = {
        ...(currentProject?.settings || {}),
        visual_density: newDensity,
        llm_model: newLlmModel,
        ...(chosenVoice
          ? { tts_model: chosenVoice.tts_model, tts_voice: chosenVoice.voice }
          : {}),
      };
      const res = await fetch('/api/projects/create-from-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: promptText,
          scene_count: newSceneCount,
          auto_produce: autoProduce,
          settings: baseSettings,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to create project');
      setProjects((prev) => [data.project, ...prev]);
      setCurrentProject(data.project);
      setChapterFilter('ALL');
      setNav('storyboard');
    } catch (err: any) {
      setErrorBanner(err.message);
    } finally {
      setBusyBanner(null);
    }
  };

  const handleSaveProjectChanges = async (updated: Project) => {
    setCurrentProject(updated);
    try {
      const res = await fetch(`/api/projects/${updated.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });
      if (res.ok) {
        const data = await res.json();
        setCurrentProject(data.project);
        setProjects((prev) =>
          prev.map((p) => (p.id === data.project.id ? data.project : p))
        );
      }
    } catch (err: any) {
      setErrorBanner(err.message);
    }
  };

  const handleUpdateSetting = (key: string, value: any) => {
    if (!currentProject) return;
    const nextSettings = { ...currentProject.settings, [key]: value };
    if (key === 'tts_model' && status) {
      const found = status.tts_models.find((m) => m.id === value);
      if (found && found.voices.length > 0) {
        nextSettings.tts_voice = found.voices[0].id;
      }
    }
    handleSaveProjectChanges({ ...currentProject, settings: nextSettings });
  };

  const handleUpdateSceneField = (sceneId: string, field: keyof SceneItem, value: any) => {
    if (!currentProject) return;
    const nextScenes = currentProject.scenes.map((sc) =>
      sc.id === sceneId
        ? {
            ...sc,
            [field]: value,
            ...(field === 'character_id' ? { use_character_ref: value !== 'diagram' } : {}),
          }
        : sc
    );
    setCurrentProject({ ...currentProject, scenes: nextScenes });
  };

  const handlePersistScene = async () => {
    if (!currentProject) return;
    await handleSaveProjectChanges(currentProject);
  };

  const handleRebuildScriptScale = async (sceneCount: number) => {
    if (!currentProject) return;
    setErrorBanner(null);
    setBusyBanner(`Re-architecting ${sceneCount}-beat long-form script across chapters...`);
    try {
      const res = await fetch(`/api/projects/${currentProject.id}/generate-script`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          topic: currentProject.topic,
          scene_count: sceneCount,
          settings: currentProject.settings,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Script generation failed');
      setCurrentProject(data.project);
      setProjects((prev) =>
        prev.map((p) => (p.id === data.project.id ? data.project : p))
      );
      setChapterFilter('ALL');
    } catch (err: any) {
      setErrorBanner(err.message);
    } finally {
      setBusyBanner(null);
    }
  };

  const handleGenerateSingleImage = async (sc: SceneItem) => {
    if (!currentProject) return;
    setSceneBusy((prev) => ({ ...prev, [sc.id]: 'image' }));
    setErrorBanner(null);
    try {
      const res = await fetch(
        `/api/projects/${currentProject.id}/scenes/${sc.id}/generate-image`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            visual_prompt: sc.visual_prompt,
            label_overlay: sc.label_overlay,
            character_id: sc.character_id,
            camera_motion: sc.camera_motion,
            sfx_cue: sc.sfx_cue,
            title: sc.title,
          }),
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Image generation failed');
      setCurrentProject(data.project);
      setProjects((prev) =>
        prev.map((p) => (p.id === data.project.id ? data.project : p))
      );
    } catch (err: any) {
      setErrorBanner(err.message);
    } finally {
      setSceneBusy((prev) => {
        const c = { ...prev };
        delete c[sc.id];
        return c;
      });
    }
  };

  const handleGenerateSingleAudio = async (sc: SceneItem) => {
    if (!currentProject) return;
    setSceneBusy((prev) => ({ ...prev, [sc.id]: 'audio' }));
    setErrorBanner(null);
    try {
      const res = await fetch(
        `/api/projects/${currentProject.id}/scenes/${sc.id}/generate-audio`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ narration: sc.narration }),
        }
      );
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Voice synthesis failed');
      setCurrentProject(data.project);
      setProjects((prev) =>
        prev.map((p) => (p.id === data.project.id ? data.project : p))
      );
    } catch (err: any) {
      setErrorBanner(err.message);
    } finally {
      setSceneBusy((prev) => {
        const c = { ...prev };
        delete c[sc.id];
        return c;
      });
    }
  };

  const handleProduceAll = async (force: boolean = false) => {
    if (!currentProject) return;
    setErrorBanner(null);
    try {
      await handleSaveProjectChanges(currentProject);
      const res = await fetch(`/api/projects/${currentProject.id}/generate-all`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to start production');
      setCurrentProject((prev) => (prev ? { ...prev, active_job: data.job } : prev));
    } catch (err: any) {
      setErrorBanner(err.message);
    }
  };

  const handlePauseJob = async () => {
    if (!currentProject) return;
    await fetch(`/api/projects/${currentProject.id}/cancel-job`, { method: 'POST' });
  };

  const handleRenderReady = async () => {
    if (!currentProject) return;
    setBusyBanner('Assembling 1080p MP4 from ready scenes & chapter cards...');
    setErrorBanner(null);
    try {
      const res = await fetch(`/api/projects/${currentProject.id}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          settings: currentProject.settings,
          ready_scenes_only: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Render failed');
      setCurrentProject(data.project);
      setProjects((prev) =>
        prev.map((p) => (p.id === data.project.id ? data.project : p))
      );
    } catch (err: any) {
      setErrorBanner(err.message);
    } finally {
      setBusyBanner(null);
    }
  };

  const handleCreateOrRegenCast = async (member?: CastMember) => {
    if (member) {
      setRegeneratingCastId(member.id);
    } else {
      if (!newCharName.trim()) {
        setErrorBanner('Enter a character name.');
        return;
      }
      setCreatingChar(true);
    }
    setErrorBanner(null);
    try {
      const payload = member
        ? {
            id: member.id,
            name: member.name,
            role: member.role,
            badge: member.badge,
            visual_description: member.visual_description,
          }
        : {
            name: newCharName.trim(),
            role: newCharRole.trim() || 'Specialist',
            badge: newCharBadge.trim() || 'Custom',
            visual_description: newCharDesc.trim(),
          };

      const res = await fetch('/api/cast/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to generate character sheet');
      if (status) {
        setStatus({ ...status, cast: data.cast });
      }
      if (!member) {
        setNewCharName('');
        setNewCharRole('');
        setNewCharBadge('');
      }
    } catch (err: any) {
      setErrorBanner(err.message);
    } finally {
      setCreatingChar(false);
      setRegeneratingCastId(null);
    }
  };

  const handleSelectFeaturedVoice = async (fv: { tts_model: string; voice: string }) => {
    if (!currentProject) return;
    await handleSaveProjectChanges({
      ...currentProject,
      settings: {
        ...currentProject.settings,
        tts_model: fv.tts_model,
        tts_voice: fv.voice,
      },
    });
  };

  const handlePreviewVoice = async (ttsModel?: string, ttsVoice?: string, customText?: string) => {
    const m = ttsModel || currentProject?.settings.tts_model || 'microsoft/mai-voice-2.1';
    const v = ttsVoice || currentProject?.settings.tts_voice || 'en-US-Grant:MAI-Voice-2.1';
    setPreviewingVoice(true);
    setErrorBanner(null);
    try {
      const res = await fetch('/api/tts/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tts_model: m,
          tts_voice: v,
          text: customText || voiceLabText,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Voice preview failed');
      setPreviewAudioUrl(data.audio_url);
      setTimeout(() => {
        audioPreviewEl.current?.play().catch(() => {});
      }, 60);
    } catch (err: any) {
      setErrorBanner(err.message);
    } finally {
      setPreviewingVoice(false);
    }
  };

  const handlePreviewSfx = async (cue: string) => {
    if (!cue || cue === 'none') return;
    try {
      const res = await fetch(`/api/sfx/preview/${cue}`);
      const data = await res.json();
      if (data.audio_url) {
        setPreviewAudioUrl(data.audio_url);
        setTimeout(() => {
          audioPreviewEl.current?.play().catch(() => {});
        }, 50);
      }
    } catch {
      // ignore
    }
  };

  const handleSaveApiKey = async () => {
    if (!apiKeyInput.trim()) return;
    try {
      const res = await fetch('/api/settings/key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKeyInput.trim() }),
      });
      const data = await res.json();
      if (res.ok && status) {
        setStatus({ ...status, api_key: data.api_key });
        setSettingsOpen(false);
        setApiKeyInput('');
      }
    } catch (err: any) {
      setErrorBanner(err.message);
    }
  };

  const handleAddScene = async () => {
    if (!currentProject) return;
    const nextNum = currentProject.scenes.length + 1;
    const newSc: SceneItem = {
      id: `scene_${String(nextNum).padStart(3, '0')}_${Math.random().toString(36).slice(2, 6)}`,
      scene_number: nextNum,
      chapter:
        chapterFilter !== 'ALL'
          ? chapterFilter
          : currentProject.scenes[currentProject.scenes.length - 1]?.chapter || 'Chapter 1',
      title: `Beat ${nextNum}`,
      character_id: 'alex',
      use_character_ref: true,
      shot_variant: 'wide',
      narration: 'You verify the primary pressure readings before advancing to the next stage.',
      visual_prompt:
        'Alex (orange cap stick-figure) inspecting a wall-mounted pressure manifold on a stark pure white (#FFFFFF) background.',
      label_overlay: '',
      camera_motion: 'zoom_in',
      sfx_cue: 'none',
      duration: 6.5,
    };
    await handleSaveProjectChanges({
      ...currentProject,
      scenes: [...currentProject.scenes, newSc],
    });
  };

  const handleDeleteScene = async (sceneId: string) => {
    if (!currentProject) return;
    const filtered = currentProject.scenes
      .filter((s) => s.id !== sceneId)
      .map((s, i) => ({ ...s, scene_number: i + 1 }));
    await handleSaveProjectChanges({ ...currentProject, scenes: filtered });
  };

  const isJobRunning = currentProject?.active_job?.status === 'running';
  const castList = status?.cast || [];
  const castMap = Object.fromEntries(castList.map((c) => [c.id, c]));

  const chapterNames = Array.from(
    new Set((currentProject?.scenes || []).map((s) => s.chapter).filter(Boolean))
  );
  const visibleScenes = (currentProject?.scenes || []).filter((s) =>
    chapterFilter === 'ALL' ? true : s.chapter === chapterFilter
  );

  // Cost calculation for New Video Modal & Economy tab
  const activeImgModel = status?.image_models.find(
    (m) => m.id === (currentProject?.settings.image_model || 'bytedance-seed/seedream-5-0-flash')
  );
  const activeTtsModel = status?.tts_models.find(
    (m) => m.id === (currentProject?.settings.tts_model || 'hexgrad/kokoro-82m')
  );
  const densityDivisor =
    newDensity === 'smart_2x' ? 2 : newDensity === 'smart_3x' ? 3 : 1;
  const estUniqueImages = Math.ceil(newSceneCount / densityDivisor);
  const estImageCost = estUniqueImages * (activeImgModel?.cost_num || 0.018);

  if (loadingInit) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-5 h-5 text-zinc-400 animate-spin" />
        <p className="text-xs font-mono text-zinc-400 tracking-wider uppercase">
          Loading Studio Workspace...
        </p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex">
      {previewAudioUrl && (
        <audio ref={audioPreviewEl} src={previewAudioUrl} className="hidden" />
      )}

      {/* SHADCN SIDEBAR NAVIGATION */}
      <aside className="w-64 border-r border-zinc-800/80 bg-zinc-950 flex flex-col justify-between shrink-0 select-none">
        <div className="p-4 space-y-5">
          {/* Brand Header */}
          <div className="flex items-center justify-between px-1">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-md bg-zinc-100 text-zinc-950 flex items-center justify-center font-bold text-xs">
                SF
              </div>
              <div>
                <div className="text-sm font-semibold tracking-tight text-zinc-100 leading-none">
                  StickForge
                </div>
                <div className="text-[11px] text-zinc-400 mt-0.5">
                  20-Min Documentary Studio
                </div>
              </div>
            </div>
          </div>

          {/* Primary Action: New Long-Form Video */}
          <Button
            onClick={() => setNewDialogOpen(true)}
            className="w-full justify-center h-9"
          >
            <Plus className="w-3.5 h-3.5" />
            New Video from Prompt
          </Button>

          {/* Main Navigation */}
          <div className="space-y-1">
            <div className="px-2 pb-1 text-[10px] font-mono uppercase tracking-wider text-zinc-500">
              Workspace
            </div>
            {[
              { id: 'storyboard', label: 'Storyboard & Timeline', icon: Clapperboard },
              { id: 'cast', label: `Cast & Characters (${castList.length})`, icon: Users },
              { id: 'engine', label: '20-Min Economy & Engine', icon: Gauge },
              { id: 'voicelab', label: 'Voices & SFX Lab', icon: AudioWaveform },
              { id: 'reference', label: 'Reference Dissector', icon: Film },
            ].map((item) => {
              const Icon = item.icon;
              const active = nav === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setNav(item.id as NavSection)}
                  className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-md text-xs font-medium transition cursor-pointer ${
                    active
                      ? 'bg-zinc-900 text-zinc-100 border border-zinc-800'
                      : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{item.label}</span>
                </button>
              );
            })}
          </div>

          {/* Projects List */}
          <div className="space-y-1.5 pt-2 border-t border-zinc-900">
            <div className="px-2 flex items-center justify-between">
              <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
                Projects ({projects.length})
              </span>
            </div>
            <div className="space-y-1 max-h-[340px] overflow-y-auto pr-0.5">
              {projects.map((p) => {
                const selected = currentProject?.id === p.id;
                const scCount = p.stats?.total_scenes ?? p.scenes?.length ?? 0;
                const durLabel = formatMinSec(
                  p.total_duration || p.stats?.estimated_duration_sec || scCount * 6.5
                );
                return (
                  <button
                    key={p.id}
                    onClick={() => handleSelectProject(p)}
                    className={`w-full text-left px-2.5 py-2 rounded-md text-xs transition cursor-pointer border ${
                      selected
                        ? 'bg-zinc-900 border-zinc-700 text-zinc-100'
                        : 'border-transparent text-zinc-400 hover:bg-zinc-900/50 hover:text-zinc-200'
                    }`}
                  >
                    <div className="font-medium truncate">{p.title}</div>
                    <div className="flex items-center justify-between text-[10px] font-mono text-zinc-500 mt-0.5">
                      <span>
                        {scCount} beats · {durLabel}
                      </span>
                      {p.video_url && (
                        <span className="text-emerald-400 font-semibold">MP4</span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Sidebar Footer: Clean Connection Status & Settings (Zero key/wallet leaks) */}
        <div className="p-3 border-t border-zinc-900 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span
              className={`w-2 h-2 rounded-full ${
                status?.api_key.configured ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
            <span>{status?.api_key.configured ? 'Pipeline Ready' : 'Key Required'}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSettingsOpen(true)}
            className="h-7 px-2"
          >
            <Settings className="w-3.5 h-3.5" />
          </Button>
        </div>
      </aside>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 max-h-screen overflow-hidden">
        {/* Top Status / Error Bar */}
        {errorBanner && (
          <div className="bg-red-950/70 border-b border-red-900/60 px-6 py-2 flex items-center justify-between text-xs text-red-200 shrink-0">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
              <span>{errorBanner}</span>
            </div>
            <button
              onClick={() => setErrorBanner(null)}
              className="text-red-300 hover:text-white font-mono text-[11px]"
            >
              Dismiss
            </button>
          </div>
        )}

        {busyBanner && (
          <div className="bg-zinc-900 border-b border-zinc-800 px-6 py-2 flex items-center gap-2.5 text-xs text-zinc-200 shrink-0">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-zinc-400" />
            <span className="font-mono">{busyBanner}</span>
          </div>
        )}

        {/* Active Background Job Progress Bar */}
        {currentProject?.active_job && currentProject.active_job.status === 'running' && (
          <div className="bg-zinc-900/90 border-b border-zinc-800 px-6 py-2.5 shrink-0">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <div className="flex items-center gap-2 font-mono text-zinc-200">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-zinc-400" />
                <span>{currentProject.active_job.detail}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-zinc-400">
                  {currentProject.active_job.percent}%
                </span>
                <Button variant="outline" size="sm" onClick={handlePauseJob}>
                  <Pause className="w-3 h-3" /> Pause
                </Button>
              </div>
            </div>
            <Progress value={currentProject.active_job.percent} />
          </div>
        )}

        {/* ==================== SECTION 1: STORYBOARD & TIMELINE ==================== */}
        {nav === 'storyboard' && currentProject && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Project Header Bar */}
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-zinc-800/80 pb-5">
              <div className="space-y-1 max-w-2xl">
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">
                    {currentProject.chapters?.length || chapterNames.length || 1} Chapters
                  </Badge>
                  <Badge variant="outline">
                    {currentProject.scenes.length} Narrative Beats
                  </Badge>
                  <Badge variant="outline">
                    {currentProject.settings.visual_density === 'smart_2x'
                      ? 'Smart 2x Multi-Angle'
                      : currentProject.settings.visual_density === 'smart_3x'
                      ? 'Ultra-Economy 3x'
                      : 'Every-Beat Unique'}
                  </Badge>
                  <Badge variant="success">
                    Est.{' '}
                    {formatMinSec(
                      currentProject.total_duration ||
                        currentProject.stats?.estimated_duration_sec ||
                        currentProject.scenes.length * 6.5
                    )}
                  </Badge>
                </div>
                <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
                  {currentProject.title}
                </h1>
                <p className="text-xs text-zinc-400 leading-relaxed">
                  {currentProject.logline || currentProject.topic}
                </p>
              </div>

              {/* Primary Production Controls */}
              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={`${currentProject.settings.tts_model}::${currentProject.settings.tts_voice}`}
                  onChange={(e) => {
                    const [m, v] = e.target.value.split('::');
                    if (m && v) handleSelectFeaturedVoice({ tts_model: m, voice: v });
                  }}
                  className="h-9 rounded-md bg-zinc-900 border border-zinc-800 px-2.5 text-xs text-zinc-200"
                  title="Select Natural Female or Male Narrator Voice"
                >
                  <optgroup label="Natural Female Narrators">
                    {status?.featured_voices
                      ?.filter((fv) => fv.gender === 'female')
                      .map((fv) => (
                        <option
                          key={fv.id}
                          value={`${fv.tts_model}::${fv.voice}`}
                        >
                          ♀ {fv.name}
                        </option>
                      ))}
                  </optgroup>
                  <optgroup label="Natural Male Narrators">
                    {status?.featured_voices
                      ?.filter((fv) => fv.gender === 'male')
                      .map((fv) => (
                        <option
                          key={fv.id}
                          value={`${fv.tts_model}::${fv.voice}`}
                        >
                          ♂ {fv.name}
                        </option>
                      ))}
                  </optgroup>
                </select>

                {!isJobRunning ? (
                  <Button onClick={() => handleProduceAll(false)} size="lg">
                    <Sparkles className="w-3.5 h-3.5" />
                    Produce Full Video ({currentProject.scenes.length} Beats)
                  </Button>
                ) : (
                  <Button variant="secondary" onClick={handlePauseJob} size="lg">
                    <Pause className="w-3.5 h-3.5" />
                    Pause Job
                  </Button>
                )}

                <Button
                  variant="outline"
                  onClick={handleRenderReady}
                  disabled={!!busyBanner}
                  title="Assemble 1080p MP4 immediately from all ready scenes"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Assemble MP4 ({currentProject.stats?.ready_images ?? 0}/
                  {currentProject.scenes.length})
                </Button>

                {currentProject.video_url && (
                  <Button variant="secondary" asChild>
                    <a
                      href={currentProject.video_url}
                      download={`${currentProject.id}.mp4`}
                    >
                      <Download className="w-3.5 h-3.5" />
                      Download MP4
                    </a>
                  </Button>
                )}

                {currentProject.srt_url && (
                  <Button variant="ghost" size="sm" asChild>
                    <a
                      href={currentProject.srt_url}
                      download={`${currentProject.id}.srt`}
                    >
                      <Subtitles className="w-3.5 h-3.5" />
                      SRT
                    </a>
                  </Button>
                )}

                {currentProject.chapters_text && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(currentProject.chapters_text || '');
                      setCopiedChapters(true);
                      setTimeout(() => setCopiedChapters(false), 2000);
                    }}
                  >
                    {copiedChapters ? (
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="w-3.5 h-3.5" />
                    )}
                    Chapters
                  </Button>
                )}
              </div>
            </div>

            {/* Top Grid: Master Cinema Player + Chapter Structure & Scale */}
            <div className="grid grid-cols-12 gap-5">
              {/* Cinema Monitor (7 cols) */}
              <Card className="col-span-12 lg:col-span-7 overflow-hidden flex flex-col justify-between">
                <CardHeader className="py-3 px-4 border-b border-zinc-800/80 flex flex-row items-center justify-between space-y-0">
                  <div className="flex items-center gap-2">
                    <Video className="w-3.5 h-3.5 text-zinc-400" />
                    <CardTitle className="text-xs font-medium">
                      Master 1080p Cinema Output
                    </CardTitle>
                  </div>
                  <div className="text-[11px] font-mono text-zinc-400">
                    {currentProject.video_url
                      ? `${formatMinSec(currentProject.total_duration)} · 1920x1080 30fps`
                      : 'Awaiting Render'}
                  </div>
                </CardHeader>
                <div className="bg-black aspect-video flex items-center justify-center relative">
                  {currentProject.video_url ? (
                    <video
                      key={currentProject.video_url}
                      src={currentProject.video_url}
                      controls
                      className="w-full h-full object-contain"
                      poster={
                        currentProject.scenes[0]?.image_url ||
                        currentProject.character_ref_url
                      }
                    />
                  ) : (
                    <div className="text-center p-8 space-y-2">
                      <Film className="w-8 h-8 text-zinc-600 mx-auto" />
                      <div className="text-xs font-medium text-zinc-300">
                        Master Video Not Assembled Yet
                      </div>
                      <p className="text-[11px] text-zinc-500 max-w-sm">
                        Click &ldquo;Produce Full Video&rdquo; to batch-generate all voiceovers
                        and master stick-figure frames, then assemble the 1080p MP4.
                      </p>
                    </div>
                  )}
                </div>
              </Card>

              {/* Chapter Outline & Scale Architect (5 cols) */}
              <Card className="col-span-12 lg:col-span-5 flex flex-col justify-between">
                <div>
                  <CardHeader className="py-3 px-4 border-b border-zinc-800/80 flex flex-row items-center justify-between space-y-0">
                    <CardTitle className="text-xs font-medium">
                      Chapter Outline & Long-Form Scale
                    </CardTitle>
                    <span className="text-[11px] font-mono text-zinc-400">
                      {currentProject.stats?.ready_images ?? 0}/
                      {currentProject.scenes.length} ready
                    </span>
                  </CardHeader>
                  <CardContent className="p-4 space-y-3">
                    <div>
                      <label className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">
                        Prompt / Premise
                      </label>
                      <Textarea
                        rows={2}
                        value={currentProject.topic}
                        onChange={(e) =>
                          setCurrentProject({ ...currentProject, topic: e.target.value })
                        }
                        onBlur={() => handleSaveProjectChanges(currentProject)}
                        className="resize-none text-xs"
                      />
                    </div>

                    <div className="space-y-1 max-h-48 overflow-y-auto pr-1">
                      {(currentProject.chapters?.length
                        ? currentProject.chapters
                        : chapterNames.map((t, i) => ({
                            title: t,
                            start_scene_index: i,
                          }))
                      ).map((ch, idx) => {
                        const active = chapterFilter === ch.title;
                        return (
                          <button
                            key={idx}
                            onClick={() =>
                              setChapterFilter(active ? 'ALL' : ch.title)
                            }
                            className={`w-full text-left px-3 py-1.5 rounded-md text-xs flex items-center justify-between transition cursor-pointer border ${
                              active
                                ? 'bg-zinc-800 border-zinc-600 text-zinc-100'
                                : 'bg-zinc-950/60 border-zinc-800/70 text-zinc-300 hover:bg-zinc-900'
                            }`}
                          >
                            <span className="truncate font-medium">
                              <span className="font-mono text-zinc-500 mr-1.5">
                                {String(idx + 1).padStart(2, '0')}
                              </span>
                              {ch.title}
                            </span>
                            {ch.scene_count && (
                              <span className="text-[10px] font-mono text-zinc-400 ml-2 shrink-0">
                                {ch.scene_count} beats
                              </span>
                            )}
                          </button>
                        );
                      })}
                    </div>
                  </CardContent>
                </div>

                {/* Quick Scale Re-Architect */}
                <div className="p-4 pt-3 border-t border-zinc-800/80 space-y-2">
                  <div className="text-[10px] font-mono uppercase text-zinc-500">
                    Re-Architect Prompt Duration:
                  </div>
                  <div className="grid grid-cols-4 gap-1.5">
                    {status?.duration_presets.map((dp) => (
                      <Button
                        key={dp.id}
                        variant="outline"
                        size="sm"
                        disabled={isJobRunning || !!busyBanner}
                        onClick={() => handleRebuildScriptScale(dp.scene_count)}
                        className="text-[10px] font-mono px-2"
                      >
                        {dp.minutes}m ({dp.scene_count})
                      </Button>
                    ))}
                  </div>
                </div>
              </Card>
            </div>

            {/* Storyboard Toolbar: Chapter Filter Pills + Layout Toggle (Cards vs Table) */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
                <Button
                  variant={chapterFilter === 'ALL' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setChapterFilter('ALL')}
                >
                  All Chapters ({currentProject.scenes.length})
                </Button>
                {chapterNames.map((chName, i) => {
                  const cnt = currentProject.scenes.filter(
                    (s) => s.chapter === chName
                  ).length;
                  return (
                    <Button
                      key={chName}
                      variant={chapterFilter === chName ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setChapterFilter(chName)}
                    >
                      {i + 1}. {chName} ({cnt})
                    </Button>
                  );
                })}
              </div>

              <div className="flex items-center gap-2">
                <div className="inline-flex rounded-md border border-zinc-800 bg-zinc-900 p-0.5">
                  <button
                    onClick={() => setLayoutMode('cards')}
                    className={`px-2.5 py-1 rounded-xs text-xs flex items-center gap-1.5 cursor-pointer ${
                      layoutMode === 'cards'
                        ? 'bg-zinc-800 text-zinc-100 font-medium'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    <Grid className="w-3.5 h-3.5" /> Cards
                  </button>
                  <button
                    onClick={() => setLayoutMode('table')}
                    className={`px-2.5 py-1 rounded-xs text-xs flex items-center gap-1.5 cursor-pointer ${
                      layoutMode === 'table'
                        ? 'bg-zinc-800 text-zinc-100 font-medium'
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    <LayoutList className="w-3.5 h-3.5" /> Compact Table
                  </button>
                </div>

                <Button variant="outline" size="sm" onClick={handleAddScene}>
                  <Plus className="w-3.5 h-3.5" /> Add Beat
                </Button>
              </div>
            </div>

            {/* VIEW MODE A: COMPACT TABLE VIEW (Ideal for scanning 96–160 scene 20-minute videos) */}
            {layoutMode === 'table' && (
              <Card className="overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-zinc-800 bg-zinc-900/70 text-[10px] font-mono uppercase text-zinc-400">
                        <th className="py-2.5 px-3 w-14">#</th>
                        <th className="py-2.5 px-3 w-36">Frame</th>
                        <th className="py-2.5 px-3 w-40">Character</th>
                        <th className="py-2.5 px-3">Narration & Visual Prompt</th>
                        <th className="py-2.5 px-3 w-36">Camera & Shot</th>
                        <th className="py-2.5 px-3 w-32 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-800/60">
                      {visibleScenes.map((sc) => {
                        const busy = sceneBusy[sc.id];
                        const charObj = castMap[sc.character_id || 'alex'];
                        return (
                          <tr key={sc.id} className="hover:bg-zinc-900/40">
                            <td className="py-3 px-3 font-mono text-zinc-400 align-top">
                              #{String(sc.scene_number).padStart(3, '0')}
                              <div className="text-[10px] text-zinc-500 mt-0.5">
                                {sc.duration || 6.5}s
                              </div>
                            </td>
                            <td className="py-3 px-3 align-top">
                              <div
                                onClick={() =>
                                  sc.image_url &&
                                  setLightbox({
                                    url: sc.image_url,
                                    title: `Beat #${sc.scene_number}: ${sc.title}`,
                                  })
                                }
                                className="w-28 aspect-video rounded border border-zinc-800 bg-zinc-950 overflow-hidden cursor-pointer flex items-center justify-center"
                              >
                                {sc.image_url ? (
                                  <img
                                    src={sc.image_url}
                                    alt={sc.title}
                                    className="w-full h-full object-cover bg-white"
                                  />
                                ) : (
                                  <ImageIcon className="w-4 h-4 text-zinc-700" />
                                )}
                              </div>
                            </td>
                            <td className="py-3 px-3 align-top">
                              <select
                                value={sc.character_id || 'alex'}
                                onChange={(e) => {
                                  handleUpdateSceneField(
                                    sc.id,
                                    'character_id',
                                    e.target.value
                                  );
                                }}
                                onBlur={handlePersistScene}
                                className="w-full bg-zinc-950 border border-zinc-800 rounded px-2 py-1 text-xs text-zinc-200"
                              >
                                {castList.map((c) => (
                                  <option key={c.id} value={c.id}>
                                    {c.name}
                                  </option>
                                ))}
                                <option value="diagram">Diagram / Cutaway Only</option>
                              </select>
                              <div className="text-[10px] font-mono text-zinc-500 mt-1 truncate">
                                {sc.chapter}
                              </div>
                            </td>
                            <td className="py-3 px-3 align-top space-y-1.5">
                              <div className="font-medium text-zinc-200">{sc.narration}</div>
                              <div className="text-[11px] font-mono text-zinc-500 line-clamp-1">
                                {sc.visual_prompt}
                              </div>
                              {sc.audio_url && (
                                <audio
                                  src={sc.audio_url}
                                  controls
                                  className="h-6 w-52 mt-1"
                                />
                              )}
                            </td>
                            <td className="py-3 px-3 align-top">
                              <Badge variant="secondary" className="mb-1">
                                {sc.shot_variant || 'wide'}
                              </Badge>
                              <div className="text-[11px] text-zinc-400">
                                {sc.camera_motion}
                              </div>
                            </td>
                            <td className="py-3 px-3 align-top text-right">
                              <div className="flex items-center justify-end gap-1">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={!!busy}
                                  onClick={() => handleGenerateSingleImage(sc)}
                                >
                                  {busy === 'image' ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    <ImageIcon className="w-3 h-3" />
                                  )}
                                </Button>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  disabled={!!busy}
                                  onClick={() => handleGenerateSingleAudio(sc)}
                                >
                                  {busy === 'audio' ? (
                                    <Loader2 className="w-3 h-3 animate-spin" />
                                  ) : (
                                    <Volume2 className="w-3 h-3" />
                                  )}
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setEditingSceneId(sc.id)}
                                >
                                  Edit
                                </Button>
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}

            {/* VIEW MODE B: CLEAN SHADCN STORYBOARD CARDS */}
            {layoutMode === 'cards' && (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                {visibleScenes.map((sc) => {
                  const busy = sceneBusy[sc.id];
                  const charObj = castMap[sc.character_id || 'alex'];
                  return (
                    <Card key={sc.id} className="overflow-hidden flex flex-col justify-between">
                      <div className="p-4 grid grid-cols-12 gap-4">
                        {/* Left 5 cols: Frame + Character Pill */}
                        <div className="col-span-5 flex flex-col justify-between space-y-2.5">
                          <div className="relative rounded-md overflow-hidden border border-zinc-800 bg-zinc-950 aspect-video group">
                            {sc.image_url ? (
                              <>
                                <img
                                  src={sc.image_url}
                                  alt={sc.title}
                                  className="w-full h-full object-cover bg-white"
                                />
                                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                                  <Button
                                    variant="secondary"
                                    size="sm"
                                    onClick={() =>
                                      setLightbox({
                                        url: sc.image_url!,
                                        title: `Beat #${sc.scene_number}: ${sc.title}`,
                                      })
                                    }
                                  >
                                    <Eye className="w-3 h-3" /> Inspect
                                  </Button>
                                </div>
                              </>
                            ) : (
                              <div className="w-full h-full flex flex-col items-center justify-center text-zinc-600 p-3 text-center">
                                <ImageIcon className="w-6 h-6 mb-1" />
                                <span className="text-[10px] font-mono">Not Drawn</span>
                              </div>
                            )}

                            <div className="absolute top-1.5 left-1.5 flex items-center gap-1">
                              <span className="px-1.5 py-0.5 rounded bg-zinc-950/90 text-zinc-100 font-mono text-[10px] font-semibold">
                                #{String(sc.scene_number).padStart(2, '0')}
                              </span>
                              {sc.shot_variant && sc.shot_variant !== 'wide' && (
                                <span className="px-1.5 py-0.5 rounded bg-zinc-900/90 text-emerald-300 font-mono text-[9px]">
                                  {sc.shot_variant === 'focus_right'
                                    ? 'Crop Right'
                                    : 'Crop Left'}
                                </span>
                              )}
                            </div>

                            <div className="absolute bottom-1.5 right-1.5">
                              <span className="px-1.5 py-0.5 rounded bg-zinc-950/90 text-zinc-300 font-mono text-[10px]">
                                {sc.duration || 6.5}s
                              </span>
                            </div>
                          </div>

                          {/* Character Selector for this Beat */}
                          <div>
                            <label className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">
                              Scene Character
                            </label>
                            <select
                              value={sc.character_id || 'alex'}
                              onChange={(e) =>
                                handleUpdateSceneField(sc.id, 'character_id', e.target.value)
                              }
                              onBlur={handlePersistScene}
                              className="w-full h-7 rounded-md bg-zinc-950 border border-zinc-800 px-2 text-xs text-zinc-200"
                            >
                              {castList.map((c) => (
                                <option key={c.id} value={c.id}>
                                  {c.name} ({c.badge})
                                </option>
                              ))}
                              <option value="diagram">Diagram / Cutaway Only</option>
                            </select>
                          </div>

                          <div className="flex items-center gap-1.5">
                            <Button
                              variant="outline"
                              size="sm"
                              className="flex-1"
                              disabled={!!busy || isJobRunning}
                              onClick={() => handleGenerateSingleImage(sc)}
                            >
                              {busy === 'image' ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <ImageIcon className="w-3 h-3" />
                              )}
                              {sc.image_url ? 'Redraw' : 'Draw'}
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              className="flex-1"
                              disabled={!!busy || isJobRunning}
                              onClick={() => handleGenerateSingleAudio(sc)}
                            >
                              {busy === 'audio' ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <Mic className="w-3 h-3" />
                              )}
                              Voice
                            </Button>
                          </div>
                        </div>

                        {/* Right 7 cols: Narration, Prompt, Motion & Audio */}
                        <div className="col-span-7 flex flex-col justify-between space-y-2.5">
                          <div className="flex items-center justify-between gap-2">
                            <div className="truncate">
                              <span className="text-[10px] font-mono uppercase text-zinc-500 block">
                                {sc.chapter}
                              </span>
                              <input
                                type="text"
                                value={sc.title}
                                onChange={(e) =>
                                  handleUpdateSceneField(sc.id, 'title', e.target.value)
                                }
                                onBlur={handlePersistScene}
                                className="bg-transparent text-xs font-semibold text-zinc-100 focus:outline-none w-full"
                              />
                            </div>
                            <button
                              onClick={() => handleDeleteScene(sc.id)}
                              className="text-zinc-600 hover:text-red-400 p-1 cursor-pointer"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>

                          <div>
                            <Textarea
                              rows={2}
                              value={sc.narration}
                              onChange={(e) =>
                                handleUpdateSceneField(sc.id, 'narration', e.target.value)
                              }
                              onBlur={handlePersistScene}
                              className="text-xs leading-relaxed resize-none"
                              placeholder="Narration..."
                            />
                            {sc.audio_url && (
                              <audio
                                key={sc.audio_url}
                                src={sc.audio_url}
                                controls
                                className="h-6 w-full mt-1.5"
                              />
                            )}
                          </div>

                          <div>
                            <label className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">
                              Visual Prompt
                            </label>
                            <Textarea
                              rows={2}
                              value={sc.visual_prompt}
                              onChange={(e) =>
                                handleUpdateSceneField(
                                  sc.id,
                                  'visual_prompt',
                                  e.target.value
                                )
                              }
                              onBlur={handlePersistScene}
                              className="text-[11px] font-mono text-zinc-300 resize-none"
                            />
                          </div>

                          <div className="grid grid-cols-3 gap-2 pt-0.5">
                            <Input
                              placeholder="Label (e.g. DAY 14)"
                              value={sc.label_overlay || ''}
                              onChange={(e) =>
                                handleUpdateSceneField(
                                  sc.id,
                                  'label_overlay',
                                  e.target.value
                                )
                              }
                              onBlur={handlePersistScene}
                              className="h-7 text-[11px] font-mono px-2"
                            />
                            <select
                              value={sc.camera_motion}
                              onChange={(e) =>
                                handleUpdateSceneField(
                                  sc.id,
                                  'camera_motion',
                                  e.target.value
                                )
                              }
                              onBlur={handlePersistScene}
                              className="h-7 rounded-md bg-zinc-950 border border-zinc-800 px-2 text-[11px] text-zinc-300"
                            >
                              {status?.camera_motions.map((cm) => (
                                <option key={cm.id} value={cm.id}>
                                  {cm.name}
                                </option>
                              ))}
                            </select>
                            <select
                              value={sc.sfx_cue}
                              onChange={(e) =>
                                handleUpdateSceneField(sc.id, 'sfx_cue', e.target.value)
                              }
                              onBlur={handlePersistScene}
                              className="h-7 rounded-md bg-zinc-950 border border-zinc-800 px-2 text-[11px] text-zinc-300"
                            >
                              {status?.sfx_cues.map((sf) => (
                                <option key={sf.id} value={sf.id}>
                                  {sf.name}
                                </option>
                              ))}
                            </select>
                          </div>
                        </div>
                      </div>
                    </Card>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ==================== SECTION 2: CAST & CHARACTERS ==================== */}
        {nav === 'cast' && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            <div className="border-b border-zinc-800/80 pb-4 flex items-center justify-between">
              <div>
                <h1 className="text-lg font-semibold text-zinc-100">
                  2D Stick-Figure Cast & Character Sheets
                </h1>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Every character is drawn on a pure #FFFFFF canvas in the Galactic Highway
                  line-art style and passed via OpenRouter <code className="font-mono">input_references</code>{' '}
                  when assigned to a scene.
                </p>
              </div>
            </div>

            {/* Cast Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {castList.map((c) => (
                <Card key={c.id} className="overflow-hidden flex flex-col justify-between">
                  <div>
                    <div
                      onClick={() =>
                        setLightbox({ url: c.reference_url, title: `${c.name} — ${c.role}` })
                      }
                      className="aspect-video bg-white border-b border-zinc-800 overflow-hidden cursor-pointer relative group"
                    >
                      <img
                        src={c.reference_url}
                        alt={c.name}
                        className="w-full h-full object-contain bg-white"
                      />
                      <div className="absolute top-2 left-2">
                        <Badge variant="default">{c.badge}</Badge>
                      </div>
                    </div>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle>{c.name}</CardTitle>
                        <span className="text-[10px] font-mono text-zinc-500">
                          id: {c.id}
                        </span>
                      </div>
                      <CardDescription>{c.role}</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <p className="text-xs text-zinc-400 font-mono leading-relaxed line-clamp-3">
                        {c.visual_description}
                      </p>
                    </CardContent>
                  </div>
                  <div className="p-4 pt-0 flex items-center justify-end">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={regeneratingCastId === c.id}
                      onClick={() => handleCreateOrRegenCast(c)}
                    >
                      {regeneratingCastId === c.id ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <RefreshCw className="w-3 h-3" />
                      )}
                      Regenerate Reference Sheet
                    </Button>
                  </div>
                </Card>
              ))}

              {/* Create New Custom Stick-Figure Character Card */}
              <Card className="border-dashed border-zinc-700 bg-zinc-950/40 flex flex-col justify-between">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Plus className="w-4 h-4" />
                    Add New Stick-Figure Character
                  </CardTitle>
                  <CardDescription>
                    Create a custom character for any historical, sci-fi, or documentary
                    setting.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">
                        Name
                      </label>
                      <Input
                        placeholder="e.g. Captain Vance"
                        value={newCharName}
                        onChange={(e) => setNewCharName(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">
                        Hat / Badge Label
                      </label>
                      <Input
                        placeholder="e.g. Navy Captain Cap"
                        value={newCharBadge}
                        onChange={(e) => setNewCharBadge(e.target.value)}
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">
                      Role
                    </label>
                    <Input
                      placeholder="e.g. Submarine Commanding Officer"
                      value={newCharRole}
                      onChange={(e) => setNewCharRole(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-mono uppercase text-zinc-500 mb-1">
                      Stick-Figure Appearance Prompt
                    </label>
                    <Textarea
                      rows={3}
                      value={newCharDesc}
                      onChange={(e) => setNewCharDesc(e.target.value)}
                      className="font-mono text-[11px]"
                    />
                  </div>
                  <Button
                    onClick={() => handleCreateOrRegenCast()}
                    disabled={creatingChar}
                    className="w-full"
                  >
                    {creatingChar ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Wand2 className="w-3.5 h-3.5" />
                    )}
                    {creatingChar
                      ? 'Drawing Stick-Figure Sheet...'
                      : 'Generate Character Sheet'}
                  </Button>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* ==================== SECTION 3: 20-MIN ECONOMY & ENGINE ==================== */}
        {nav === 'engine' && currentProject && status && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-5xl">
            <div className="border-b border-zinc-800/80 pb-4">
              <h1 className="text-lg font-semibold text-zinc-100">
                20-Minute Smart Economy & Quality Engine
              </h1>
              <p className="text-xs text-zinc-400 mt-0.5">
                How we produce 15–20+ minute long-form videos for under ~$0.60–$1.20 while
                sharpening visual consistency and pacing.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Visual Density / Multi-Angle Reuse */}
              <Card>
                <CardHeader>
                  <CardTitle>1. Smart Multi-Angle Image Reuse</CardTitle>
                  <CardDescription>
                    Instead of paying for 160 separate images for a 20-minute video, generate
                    wide dual-subject master illustrations and cut between Wide, Left-Focus,
                    and Right-Focus camera framings.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2.5">
                  {status.visual_density_modes.map((vm) => {
                    const selected = currentProject.settings.visual_density === vm.id;
                    return (
                      <div
                        key={vm.id}
                        onClick={() => handleUpdateSetting('visual_density', vm.id)}
                        className={`p-3 rounded-md border cursor-pointer transition ${
                          selected
                            ? 'bg-zinc-800/90 border-zinc-500 text-zinc-100'
                            : 'bg-zinc-950/60 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                        }`}
                      >
                        <div className="text-xs font-semibold text-zinc-100">
                          {vm.name}
                        </div>
                        <p className="text-[11px] text-zinc-400 mt-1">{vm.description}</p>
                      </div>
                    );
                  })}
                </CardContent>
              </Card>

              {/* Model & Voice Cost Optimization */}
              <Card>
                <CardHeader>
                  <CardTitle>2. OpenRouter Model & Voice Routing</CardTitle>
                  <CardDescription>
                    Pair Seedream 5.0 Flash ($0.018/img) with Kokoro 82M ($0.005 per 20-min
                    video) or Zero-Shot Cloned Voice ($0.04 per 20-min video).
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div>
                    <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1">
                      Showrunner Writer Model (Anti-Slop)
                    </label>
                    <select
                      value={currentProject.settings.llm_model}
                      onChange={(e) => handleUpdateSetting('llm_model', e.target.value)}
                      className="w-full h-8 rounded-md bg-zinc-950 border border-zinc-800 px-3 text-xs text-zinc-100"
                    >
                      {status.llm_models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1">
                      OpenRouter Image Model
                    </label>
                    <select
                      value={currentProject.settings.image_model}
                      onChange={(e) => handleUpdateSetting('image_model', e.target.value)}
                      className="w-full h-8 rounded-md bg-zinc-950 border border-zinc-800 px-3 text-xs text-zinc-100"
                    >
                      {status.image_models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name} ({m.price_est})
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1">
                      OpenRouter TTS Engine
                    </label>
                    <select
                      value={currentProject.settings.tts_model}
                      onChange={(e) => handleUpdateSetting('tts_model', e.target.value)}
                      className="w-full h-8 rounded-md bg-zinc-950 border border-zinc-800 px-3 text-xs text-zinc-100"
                    >
                      {status.tts_models.map((m) => (
                        <option key={m.id} value={m.id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1">
                      Narrator Voice
                    </label>
                    <select
                      value={currentProject.settings.tts_voice}
                      onChange={(e) => handleUpdateSetting('tts_voice', e.target.value)}
                      className="w-full h-8 rounded-md bg-zinc-950 border border-zinc-800 px-3 text-xs text-zinc-100"
                    >
                      {activeTtsModel?.voices.map((v) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="pt-2 space-y-2 border-t border-zinc-800/80">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-300">
                        Zero-Cost PIL Chapter Title Cards
                      </span>
                      <Switch
                        checked={currentProject.settings.include_chapter_cards ?? true}
                        onCheckedChange={(v) =>
                          handleUpdateSetting('include_chapter_cards', v)
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-300">Procedural Survival SFX Cues</span>
                      <Switch
                        checked={currentProject.settings.include_sfx}
                        onCheckedChange={(v) => handleUpdateSetting('include_sfx', v)}
                      />
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-zinc-300">
                        20s Phase-Continuous Ambient Drone Loop
                      </span>
                      <Switch
                        checked={currentProject.settings.include_ambient}
                        onCheckedChange={(v) => handleUpdateSetting('include_ambient', v)}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* 20-Minute Cost Comparison Table */}
            <Card>
              <CardHeader>
                <CardTitle>20-Minute Video (160 Beats · 12 Chapters) Cost Breakdown</CardTitle>
                <CardDescription>
                  Comparison of total OpenRouter generation cost for a full 20-minute (1,200s)
                  episode.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-zinc-800 text-[10px] font-mono uppercase text-zinc-400">
                      <th className="py-2">Pipeline Configuration</th>
                      <th className="py-2">Visual Cuts</th>
                      <th className="py-2">Unique AI Images</th>
                      <th className="py-2">20m Voice Cost</th>
                      <th className="py-2 text-right">Total 20-Min Episode Cost</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-zinc-800/60 font-mono">
                    <tr>
                      <td className="py-2.5 text-zinc-200">
                        Ultra-Economy 3x + Seedream 5.0 Flash + Kokoro 82M
                      </td>
                      <td className="py-2.5">172 cuts (incl. 12 chapter cards)</td>
                      <td className="py-2.5">54 images</td>
                      <td className="py-2.5 text-emerald-400">$0.005</td>
                      <td className="py-2.5 text-right font-bold text-emerald-400">
                        ~$0.98 total
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 text-zinc-200">
                        Smart 2x Multi-Angle + Seedream 5.0 Flash + Cloned Narrator
                      </td>
                      <td className="py-2.5">172 cuts (incl. 12 chapter cards)</td>
                      <td className="py-2.5">80 images</td>
                      <td className="py-2.5 text-emerald-400">$0.040</td>
                      <td className="py-2.5 text-right font-bold text-zinc-100">
                        ~$1.48 total
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2.5 text-zinc-400">
                        Naive Every-Beat + Nano Banana 2.1 + ElevenLabs
                      </td>
                      <td className="py-2.5">160 cuts</td>
                      <td className="py-2.5">160 images</td>
                      <td className="py-2.5">$0.350</td>
                      <td className="py-2.5 text-right text-zinc-400">~$6.11 total</td>
                    </tr>
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </div>
        )}

        {/* ==================== SECTION 4: VOICE & SFX LAB ==================== */}
        {nav === 'voicelab' && status && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-6xl">
            <div className="border-b border-zinc-800/80 pb-4 flex items-center justify-between">
              <div>
                <h1 className="text-lg font-semibold text-zinc-100">
                  Human-Realism Voices (Female & Male) · Shure SM7B Studio Mastered
                </h1>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Curated non-AI sounding female and male voices from Microsoft MAI-Voice 2.1
                  (#1 Audio Realism), Google Gemini 3.8 TTS (#1 Overall ELO), ElevenLabs v3
                  Conversational, and Sesame CSM-1B — mastered with warm 165Hz chest EQ and
                  4.2kHz de-essing.
                </p>
              </div>
            </div>

            {/* Side-by-Side Curated Female & Male Voices with Instant Audio Players */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* Female Column */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-mono uppercase tracking-wider text-zinc-300">
                    Natural Female Narrators (6 Voices)
                  </h2>
                  <Badge variant="secondary">Female</Badge>
                </div>
                {status.featured_voices
                  ?.filter((fv) => fv.gender === 'female')
                  .map((fv) => {
                    const isSelected =
                      currentProject?.settings.tts_model === fv.tts_model &&
                      currentProject?.settings.tts_voice === fv.voice;
                    return (
                      <Card
                        key={fv.id}
                        className={
                          isSelected
                            ? 'border-zinc-400 bg-zinc-900'
                            : 'bg-zinc-950/60'
                        }
                      >
                        <CardContent className="p-3.5 space-y-2.5">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="text-xs font-semibold text-zinc-100">
                                {fv.name}
                              </div>
                              <div className="text-[11px] text-zinc-400">
                                {fv.subtitle}
                              </div>
                            </div>
                            <Badge variant={isSelected ? 'success' : 'secondary'}>
                              {isSelected ? 'Active on Project' : fv.badge}
                            </Badge>
                          </div>
                          <div className="flex items-center justify-between gap-3 pt-1">
                            {fv.preview_url ? (
                              <audio
                                src={fv.preview_url}
                                controls
                                className="h-7 flex-1"
                              />
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  handlePreviewVoice(fv.tts_model, fv.voice)
                                }
                              >
                                <Play className="w-3 h-3" /> Preview
                              </Button>
                            )}
                            <Button
                              variant={isSelected ? 'default' : 'outline'}
                              size="sm"
                              onClick={() => handleSelectFeaturedVoice(fv)}
                            >
                              {isSelected ? 'Selected' : 'Use Voice'}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
              </div>

              {/* Male Column */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h2 className="text-xs font-mono uppercase tracking-wider text-zinc-300">
                    Natural Male Narrators (6 Voices)
                  </h2>
                  <Badge variant="secondary">Male</Badge>
                </div>
                {status.featured_voices
                  ?.filter((fv) => fv.gender === 'male')
                  .map((fv) => {
                    const isSelected =
                      currentProject?.settings.tts_model === fv.tts_model &&
                      currentProject?.settings.tts_voice === fv.voice;
                    return (
                      <Card
                        key={fv.id}
                        className={
                          isSelected
                            ? 'border-zinc-400 bg-zinc-900'
                            : 'bg-zinc-950/60'
                        }
                      >
                        <CardContent className="p-3.5 space-y-2.5">
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <div className="text-xs font-semibold text-zinc-100">
                                {fv.name}
                              </div>
                              <div className="text-[11px] text-zinc-400">
                                {fv.subtitle}
                              </div>
                            </div>
                            <Badge variant={isSelected ? 'success' : 'secondary'}>
                              {isSelected ? 'Active on Project' : fv.badge}
                            </Badge>
                          </div>
                          <div className="flex items-center justify-between gap-3 pt-1">
                            {fv.preview_url ? (
                              <audio
                                src={fv.preview_url}
                                controls
                                className="h-7 flex-1"
                              />
                            ) : (
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() =>
                                  handlePreviewVoice(fv.tts_model, fv.voice)
                                }
                              >
                                <Play className="w-3 h-3" /> Preview
                              </Button>
                            )}
                            <Button
                              variant={isSelected ? 'default' : 'outline'}
                              size="sm"
                              onClick={() => handleSelectFeaturedVoice(fv)}
                            >
                              {isSelected ? 'Selected' : 'Use Voice'}
                            </Button>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  })}
              </div>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Custom Line Audition Across Full Engine Catalog</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <Textarea
                  rows={2}
                  value={voiceLabText}
                  onChange={(e) => setVoiceLabText(e.target.value)}
                />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {status.tts_models.map((tm) => (
                    <Card key={tm.id} className="bg-zinc-950/60">
                      <CardHeader className="pb-2">
                        <div className="flex items-center justify-between">
                          <CardTitle className="text-xs">{tm.name}</CardTitle>
                          <Badge variant="secondary">{tm.badge}</Badge>
                        </div>
                      </CardHeader>
                      <CardContent className="flex flex-wrap gap-1.5">
                        {tm.voices.map((v) => (
                          <Button
                            key={v.id}
                            variant="outline"
                            size="sm"
                            disabled={previewingVoice}
                            onClick={() => handlePreviewVoice(tm.id, v.id, voiceLabText)}
                          >
                            <Play className="w-3 h-3" />
                            {v.name}
                          </Button>
                        ))}
                      </CardContent>
                    </Card>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Procedural Sound Effects (24kHz WAV)</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-2.5">
                {status.sfx_cues
                  .filter((s) => s.id !== 'none')
                  .map((sfx) => (
                    <Button
                      key={sfx.id}
                      variant="outline"
                      onClick={() => handlePreviewSfx(sfx.id)}
                      className="justify-between h-10"
                    >
                      <span className="truncate">{sfx.name}</span>
                      <Volume2 className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                    </Button>
                  ))}
              </CardContent>
            </Card>
          </div>
        )}

        {/* ==================== SECTION 5: REFERENCE DISSECTOR ==================== */}
        {nav === 'reference' && refData && (
          <div className="flex-1 overflow-y-auto p-6 space-y-6 max-w-6xl">
            <div className="border-b border-zinc-800/80 pb-4 flex items-center justify-between">
              <div>
                <h1 className="text-lg font-semibold text-zinc-100">
                  Reference Dissector: {refData.reference.title} ({refData.reference.channel})
                </h1>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Downloaded via yt-dlp (`RmyjNoz2pw4`) · {refData.reference.duration_string}{' '}
                  · {refData.pacing_stats.total_cuts} cuts ({refData.pacing_stats.median_shot_seconds}s
                  median cut)
                </p>
              </div>
            </div>

            <div className="grid grid-cols-12 gap-5">
              <Card className="col-span-12 lg:col-span-7 overflow-hidden">
                <div className="bg-black aspect-video">
                  <video
                    ref={refVideoEl}
                    src={refData.reference.video_url}
                    controls
                    className="w-full h-full object-contain"
                  />
                </div>
                <CardContent className="p-4 flex items-center justify-between">
                  <div>
                    <div className="text-xs font-medium text-zinc-200">
                      Isolated Narrator Voice Cloning Sample (`narrator_sample.wav`)
                    </div>
                    <div className="text-[11px] text-zinc-500">
                      Used by Fish Audio S2.1 Pro for zero-shot narrator cloning
                    </div>
                  </div>
                  <audio
                    src={refData.reference.narrator_sample_url}
                    controls
                    className="h-8"
                  />
                </CardContent>
              </Card>

              <Card className="col-span-12 lg:col-span-5">
                <CardHeader>
                  <CardTitle>Reference Chapters (Click to Seek)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1.5 max-h-80 overflow-y-auto">
                  {refData.reference.chapters.map((ch, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        if (refVideoEl.current) {
                          refVideoEl.current.currentTime = ch.start_time;
                          refVideoEl.current.play();
                        }
                      }}
                      className="w-full text-left px-3 py-1.5 rounded border border-zinc-800 bg-zinc-950 hover:bg-zinc-900 text-xs flex items-center justify-between cursor-pointer"
                    >
                      <span className="text-zinc-200">{ch.title}</span>
                      <span className="font-mono text-zinc-400">
                        {Math.floor(ch.start_time / 60)}:
                        {String(ch.start_time % 60).padStart(2, '0')}
                      </span>
                    </button>
                  ))}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle>Extracted Reference Keyframes</CardTitle>
              </CardHeader>
              <CardContent className="grid grid-cols-4 md:grid-cols-8 gap-2">
                {refData.opening_frames.slice(0, 8).map((url, i) => (
                  <img
                    key={url}
                    src={url}
                    alt={`Opening ${i}`}
                    onClick={() =>
                      setLightbox({ url, title: `Reference Opening Beat #${i + 1}` })
                    }
                    className="rounded border border-zinc-800 h-16 w-full object-cover bg-white cursor-pointer hover:border-zinc-500"
                  />
                ))}
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* ==================== MODAL: NEW LONG-FORM VIDEO FROM PROMPT ==================== */}
      <Dialog open={newDialogOpen} onOpenChange={setNewDialogOpen}>
        <DialogContent className="max-w-2xl">
          <div className="space-y-4">
            <div>
              <Badge variant="secondary" className="mb-2">
                Prompt → 20-Min Stick-Figure Documentary
              </Badge>
              <h2 className="text-base font-semibold text-zinc-100">
                Create New Long-Form Video
              </h2>
              <p className="text-xs text-zinc-400 mt-0.5">
                Enter any topic or scenario. We keep the 2D stick-figure drawing style,
                assign recurring cast members, and expand all chapters in parallel.
              </p>
            </div>

            <div>
              <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1.5">
                Video Prompt / Topic
              </label>
              <Textarea
                rows={3}
                value={newPrompt}
                onChange={(e) => setNewPrompt(e.target.value)}
                placeholder="e.g., How 130 crew survive 6 months submerged in a nuclear submarine — oxygen electrolysis, CO2 scrubbers, watch rotations, and surviving a saltwater pipe rupture at 800 feet..."
              />
            </div>

            {/* Duration Presets */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="text-[11px] font-mono uppercase text-zinc-400">
                  Target Video Length
                </label>
                <span className="text-xs font-mono text-emerald-400">
                  Est. {formatMinSec(newSceneCount * 6.8)} · {estUniqueImages} unique images
                  (~${estImageCost.toFixed(2)})
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2">
                {status?.duration_presets.map((dp) => {
                  const active = newSceneCount === dp.scene_count;
                  return (
                    <button
                      key={dp.id}
                      onClick={() => setNewSceneCount(dp.scene_count)}
                      className={`p-2.5 rounded-md border text-left transition cursor-pointer ${
                        active
                          ? 'bg-zinc-800 border-zinc-500 text-zinc-100'
                          : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                      }`}
                    >
                      <div className="text-xs font-semibold text-zinc-100">
                        {dp.name}
                      </div>
                      <div className="text-[10px] text-zinc-400 mt-0.5">{dp.desc}</div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Writer LLM & Narrator Voice Row in New Video Modal */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1.5">
                  Showrunner Writer Model (Anti-Slop)
                </label>
                <select
                  value={newLlmModel}
                  onChange={(e) => setNewLlmModel(e.target.value)}
                  className="w-full h-8 rounded-md bg-zinc-950 border border-zinc-800 px-3 text-xs text-zinc-100"
                >
                  {status?.llm_models.map((lm) => (
                    <option key={lm.id} value={lm.id}>
                      {lm.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1.5">
                  Narrator Voice (Natural Female & Male)
                </label>
                <select
                  value={newVoicePresetId}
                  onChange={(e) => setNewVoicePresetId(e.target.value)}
                  className="w-full h-8 rounded-md bg-zinc-950 border border-zinc-800 px-3 text-xs text-zinc-100"
                >
                  <optgroup label="Natural Female Narrators">
                    {status?.featured_voices
                      ?.filter((fv) => fv.gender === 'female')
                      .map((fv) => (
                        <option key={fv.id} value={fv.id}>
                          ♀ {fv.name}
                        </option>
                      ))}
                  </optgroup>
                  <optgroup label="Natural Male Narrators">
                    {status?.featured_voices
                      ?.filter((fv) => fv.gender === 'male')
                      .map((fv) => (
                        <option key={fv.id} value={fv.id}>
                          ♂ {fv.name}
                        </option>
                      ))}
                  </optgroup>
                </select>
              </div>
            </div>

            {/* Visual Economy Mode */}
            <div>
              <label className="block text-[11px] font-mono uppercase text-zinc-400 mb-1.5">
                Visual Economy & Camera Cut Mode
              </label>
              <div className="grid grid-cols-3 gap-2">
                {status?.visual_density_modes.map((vm) => {
                  const active = newDensity === vm.id;
                  return (
                    <button
                      key={vm.id}
                      onClick={() => setNewDensity(vm.id)}
                      className={`p-2.5 rounded-md border text-left transition cursor-pointer ${
                        active
                          ? 'bg-zinc-800 border-zinc-500 text-zinc-100'
                          : 'bg-zinc-950 border-zinc-800 text-zinc-400 hover:border-zinc-700'
                      }`}
                    >
                      <div className="text-xs font-semibold text-zinc-100">
                        {vm.id === 'smart_2x'
                          ? 'Smart 2x (50% Off)'
                          : vm.id === 'smart_3x'
                          ? 'Economy 3x (67% Off)'
                          : 'Every Beat (1:1)'}
                      </div>
                      <div className="text-[10px] text-zinc-400 mt-0.5 line-clamp-2">
                        {vm.description}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Quick Starter Ideas */}
            <div>
              <div className="text-[10px] font-mono uppercase text-zinc-500 mb-1.5">
                Or Click a 12-to-20 Minute Documentary Prompt Idea:
              </div>
              <div className="grid grid-cols-2 gap-2 max-h-36 overflow-y-auto pr-1">
                {status?.starter_templates.map((tpl) => (
                  <button
                    key={tpl.id}
                    onClick={() => {
                      setNewPrompt(tpl.topic);
                      setNewSceneCount(tpl.scene_count);
                    }}
                    className="p-2 rounded border border-zinc-800 bg-zinc-900/50 hover:bg-zinc-900 text-left transition cursor-pointer"
                  >
                    <div className="text-xs font-medium text-zinc-200 truncate">
                      {tpl.title}
                    </div>
                    <div className="text-[10px] font-mono text-zinc-500">
                      {tpl.category} · {tpl.scene_count} beats
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-zinc-800">
              <Button variant="ghost" onClick={() => setNewDialogOpen(false)}>
                Cancel
              </Button>
              <Button variant="outline" onClick={() => handleLaunchFromPrompt(false)}>
                Generate {newSceneCount}-Beat Storyboard First
              </Button>
              <Button onClick={() => handleLaunchFromPrompt(true)}>
                <Sparkles className="w-3.5 h-3.5" />
                Auto-Produce Full Video
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ==================== MODAL: SETTINGS (PRIVATE API KEY INPUT) ==================== */}
      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
        <DialogContent className="max-w-md">
          <div className="space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-zinc-100">
                Pipeline API Configuration
              </h3>
              <p className="text-xs text-zinc-400 mt-1">
                Status:{' '}
                <span className="text-emerald-400 font-medium">
                  {status?.api_key.configured ? 'Configured & Private' : 'Not Configured'}
                </span>
                . Keys and balances are never displayed in the UI.
              </p>
            </div>
            <Input
              type="password"
              placeholder="Enter new OpenRouter API key to override..."
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setSettingsOpen(false)}>
                Close
              </Button>
              <Button onClick={handleSaveApiKey}>Update Key</Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      {/* ==================== MODAL: SCENE INSPECTOR (FROM COMPACT TABLE) ==================== */}
      <Dialog
        open={!!editingSceneId}
        onOpenChange={(open) => {
          if (!open) {
            handlePersistScene();
            setEditingSceneId(null);
          }
        }}
      >
        <DialogContent className="max-w-lg">
          {(() => {
            const sc = currentProject?.scenes.find((s) => s.id === editingSceneId);
            if (!sc) return null;
            return (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-zinc-100">
                    Edit Beat #{sc.scene_number}: {sc.title}
                  </h3>
                  <Badge variant="secondary">{sc.chapter}</Badge>
                </div>
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                    Character
                  </label>
                  <select
                    value={sc.character_id || 'alex'}
                    onChange={(e) =>
                      handleUpdateSceneField(sc.id, 'character_id', e.target.value)
                    }
                    className="w-full h-8 rounded-md bg-zinc-950 border border-zinc-800 px-2.5 text-xs text-zinc-200"
                  >
                    {castList.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.badge})
                      </option>
                    ))}
                    <option value="diagram">Diagram / Cutaway Only</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                    Narration
                  </label>
                  <Textarea
                    rows={3}
                    value={sc.narration}
                    onChange={(e) =>
                      handleUpdateSceneField(sc.id, 'narration', e.target.value)
                    }
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-mono uppercase text-zinc-400 mb-1">
                    Visual Prompt
                  </label>
                  <Textarea
                    rows={3}
                    value={sc.visual_prompt}
                    onChange={(e) =>
                      handleUpdateSceneField(sc.id, 'visual_prompt', e.target.value)
                    }
                    className="font-mono text-[11px]"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button
                    onClick={() => {
                      handlePersistScene();
                      setEditingSceneId(null);
                    }}
                  >
                    Save & Close
                  </Button>
                </div>
              </div>
            );
          })()}
        </DialogContent>
      </Dialog>

      {/* ==================== MODAL: LIGHTBOX ==================== */}
      {lightbox && (
        <div
          onClick={() => setLightbox(null)}
          className="fixed inset-0 z-50 bg-black/85 backdrop-blur-xs flex items-center justify-center p-8"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-w-4xl w-full bg-zinc-950 border border-zinc-800 rounded-lg overflow-hidden"
          >
            <div className="px-4 py-2.5 border-b border-zinc-800 flex items-center justify-between text-xs">
              <span className="font-mono text-zinc-200">{lightbox.title}</span>
              <button
                onClick={() => setLightbox(null)}
                className="text-zinc-400 hover:text-white font-mono cursor-pointer"
              >
                CLOSE
              </button>
            </div>
            <img
              src={lightbox.url}
              alt={lightbox.title}
              className="w-full max-h-[80vh] object-contain bg-white"
            />
          </div>
        </div>
      )}
    </div>
  );
}
