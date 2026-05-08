import { useEffect, useState } from 'react';
import type { User } from '../api';

type Props = {
  user: User;
  className: string;
  fallbackClassName: string;
  alt?: string;
};

const AVATAR_KEY = 'lobcut.profileAvatar';
const AVATAR_EVENT = 'lobcut-avatar-updated';

export function getStoredAvatar() {
  try {
    return window.localStorage.getItem(AVATAR_KEY) || '';
  } catch {
    return '';
  }
}

export function setStoredAvatar(value: string) {
  try {
    if (value) {
      window.localStorage.setItem(AVATAR_KEY, value);
    } else {
      window.localStorage.removeItem(AVATAR_KEY);
    }
    window.dispatchEvent(new Event(AVATAR_EVENT));
  } catch {
    window.dispatchEvent(new Event(AVATAR_EVENT));
  }
}

export function UserAvatar({ user, className, fallbackClassName, alt }: Props) {
  const [storedAvatar, setStoredAvatarState] = useState(() => getStoredAvatar());
  const [imageFailed, setImageFailed] = useState(false);
  const fallback = (user.name || user.email || 'U')[0].toUpperCase();
  const src = storedAvatar || user.picture || '';

  useEffect(() => {
    const syncAvatar = () => {
      setStoredAvatarState(getStoredAvatar());
      setImageFailed(false);
    };
    window.addEventListener(AVATAR_EVENT, syncAvatar);
    window.addEventListener('storage', syncAvatar);
    return () => {
      window.removeEventListener(AVATAR_EVENT, syncAvatar);
      window.removeEventListener('storage', syncAvatar);
    };
  }, []);

  useEffect(() => {
    setImageFailed(false);
  }, [src]);

  if (!src || imageFailed) {
    return <span className={fallbackClassName}>{fallback}</span>;
  }

  return (
    <img
      className={className}
      src={src}
      alt={alt || user.name || 'Profile'}
      referrerPolicy="no-referrer"
      onError={() => setImageFailed(true)}
    />
  );
}
