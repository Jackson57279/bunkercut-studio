export interface CastMember {
  id: string;
  name: string;
  role: string;
  badge: string;
  accent: string;
  default_voice: string;
  visual_description: string;
  reference_url: string;
  ready?: boolean;
}

export interface DurationPreset {
  id: string;
  name: string;
  minutes: number;
  scene_count: number;
  chapters: number;
  desc: string;
}

export interface VisualDensityMode {
  id: 'smart_2x' | 'smart_3x' | 'every_beat';
  name: string;
  divisor: number;
  description: string;
}

export interface ImageModel {
  id: string;
  name: string;
  badge: string;
  price_est: string;
  cost_num: number;
  supports_reference: boolean;
}

export interface VoiceOption {
  id: string;
  name: string;
}

export interface TTSModel {
  id: string;
  name: string;
  badge: string;
  mode: string;
  cost_per_20m?: string;
  voices: VoiceOption[];
}

export interface LLMModel {
  id: string;
  name: string;
}

export interface StylePreset {
  id: string;
  name: string;
  description: string;
  prompt_prefix: string;
  character_desc: string;
}

export interface StarterTemplate {
  id: string;
  category?: string;
  title: string;
  topic: string;
  scene_count: number;
}

export interface OptionItem {
  id: string;
  name: string;
}

export interface FeaturedVoice {
  id: string;
  gender: 'female' | 'male';
  name: string;
  subtitle: string;
  tts_model: string;
  voice: string;
  badge: string;
  preview_url?: string | null;
}

export interface StudioStatus {
  api_key: {
    configured: boolean;
  };
  cast: CastMember[];
  featured_voices: FeaturedVoice[];
  duration_presets: DurationPreset[];
  visual_density_modes: VisualDensityMode[];
  image_models: ImageModel[];
  tts_models: TTSModel[];
  llm_models: LLMModel[];
  style_presets: StylePreset[];
  starter_templates: StarterTemplate[];
  sfx_cues: OptionItem[];
  camera_motions: OptionItem[];
}

export interface SceneItem {
  id: string;
  scene_number: number;
  chapter: string;
  title: string;
  character_id: string;
  use_character_ref: boolean;
  shot_variant?: 'wide' | 'focus_left' | 'focus_right';
  narration: string;
  visual_prompt: string;
  label_overlay?: string;
  camera_motion: string;
  sfx_cue: string;
  image_file?: string | null;
  audio_file?: string | null;
  clip_file?: string | null;
  image_url?: string | null;
  audio_url?: string | null;
  clip_url?: string | null;
  duration: number;
  last_image_model?: string;
  last_tts_model?: string;
}

export interface ProjectSettings {
  style_id: string;
  image_model: string;
  tts_model: string;
  tts_voice: string;
  llm_model: string;
  visual_density: 'smart_2x' | 'smart_3x' | 'every_beat';
  aspect_ratio: '16:9' | '9:16';
  caption_style: 'none' | 'documentary' | 'kinetic';
  include_sfx: boolean;
  include_ambient: boolean;
  include_chapter_cards: boolean;
}

export interface ActiveJob {
  status: 'running' | 'completed' | 'error';
  stage: string;
  detail: string;
  completed: number;
  total: number;
  percent: number;
}

export interface ChapterMeta {
  title: string;
  summary?: string;
  start_scene_index: number;
  scene_count?: number;
}

export interface Project {
  id: string;
  title: string;
  logline: string;
  topic: string;
  created_at: number;
  updated_at: number;
  settings: ProjectSettings;
  chapters: ChapterMeta[];
  scenes: SceneItem[];
  video_file: string | null;
  srt_file: string | null;
  chapters_text?: string;
  video_url: string | null;
  srt_url: string | null;
  character_ref_url: string;
  total_duration: number;
  stats?: {
    total_scenes: number;
    ready_images: number;
    unique_images?: number;
    ready_audios: number;
    estimated_duration_sec: number;
  };
  active_job?: ActiveJob | null;
}

export interface ReferenceAnalysis {
  reference: {
    id: string;
    title: string;
    channel: string;
    duration: number;
    duration_string: string;
    resolution: string;
    fps: number;
    description: string;
    chapters: { title: string; start_time: number; end_time: number }[];
    video_url: string;
    narrator_sample_url: string;
  };
  opening_frames: string[];
  overview_frames: string[];
  transcript_preview: string[];
  pacing_stats: {
    total_cuts: number;
    avg_shot_seconds: number;
    median_shot_seconds: number;
    visual_style: string;
  };
}
