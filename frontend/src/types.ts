export interface User {
  id: number;
  name: string;
  username: string;
  role: "member";
  active: boolean;
}

export interface DocumentSet {
  id: number;
  slug: string;
  name: string;
  description: string;
  created_at: string;
  questionnaire_version: number | null;
  current_template_count: number;
}

export interface Question {
  variable_name: string;
  question_text: string;
  type: "yesno" | "choice" | "text" | "textarea";
  options: string[];
  example: string;
  skip_if: string;
  section: string;
}

export interface Questionnaire {
  version_id: number;
  questions: Question[];
}

export interface Version {
  id: number;
  version_no: number;
  is_current: number;
  uploaded_by: string;
  uploaded_at: string;
  note: string;
  label?: string;
}

export interface VersionHistory {
  questionnaires: Version[];
  templates: Version[];
}
