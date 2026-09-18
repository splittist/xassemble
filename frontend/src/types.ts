export interface User {
  id: number;
  name: string;
  username: string;
  role: "member" | "admin";
  active: boolean;
  must_change_password: boolean;
}

export interface ManagedUser extends User {
  created_at: string;
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
  examples: string[];
  commentary: string;
  skip_if: string;
  section: string;
}

export interface Questionnaire {
  version_id: number;
  schema_sha256: string;
  questions: Question[];
}

export type Answers = Record<string, string | boolean | null>;

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
