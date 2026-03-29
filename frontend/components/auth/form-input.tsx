'use client';

import { Eye, EyeOff } from 'lucide-react';
import { useId, useState } from 'react';

type FormInputProps = {
  label: string;
  name: string;
  type?: 'text' | 'email' | 'password' | 'tel';
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  disabled?: boolean;
  required?: boolean;
  error?: string;
};

export function FormInput({
  label,
  name,
  type = 'text',
  value,
  onChange,
  placeholder,
  autoComplete,
  disabled = false,
  required = false,
  error,
}: FormInputProps) {
  const inputId = useId();
  const [showPassword, setShowPassword] = useState(false);
  const resolvedType = type === 'password' ? (showPassword ? 'text' : 'password') : type;

  return (
    <label className="auth-field" htmlFor={inputId}>
      <span className="auth-field-label">{label}</span>
      <div className={error ? 'auth-input-wrap has-error' : 'auth-input-wrap'}>
        <input
          id={inputId}
          name={name}
          type={resolvedType}
          value={value}
          placeholder={placeholder}
          autoComplete={autoComplete}
          required={required}
          disabled={disabled}
          aria-invalid={error ? 'true' : 'false'}
          aria-describedby={error ? `${inputId}-error` : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
        {type === 'password' ? (
          <button
            type="button"
            className="auth-password-toggle"
            onClick={() => setShowPassword((current) => !current)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            disabled={disabled}
          >
            {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
          </button>
        ) : null}
      </div>
      {error ? (
        <span id={`${inputId}-error`} className="auth-field-error" role="alert">
          {error}
        </span>
      ) : null}
    </label>
  );
}
