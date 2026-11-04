import React from 'react';

interface BookCoverProps {
  title: string;
  author: string;
  category: string;
}

export const BookCover: React.FC<BookCoverProps> = ({ title, author, category }) => {
  const normCategory = category.toLowerCase();
  let themeClass = 'cover-default';

  if (normCategory.includes('computer') || normCategory.includes('software') || normCategory.includes('code')) {
    themeClass = 'cover-cs';
  } else if (normCategory.includes('ai') || normCategory.includes('intelligence') || normCategory.includes('learning')) {
    themeClass = 'cover-ai';
  } else if (normCategory.includes('math') || normCategory.includes('algebra') || normCategory.includes('calculus')) {
    themeClass = 'cover-math';
  } else if (normCategory.includes('physic') || normCategory.includes('science')) {
    themeClass = 'cover-physics';
  }

  return (
    <div className={`book-cover-container ${themeClass}`}>
      <div className="book-cover-mockup">
        <div className="cover-category-strip">{category || 'Monograph'}</div>
        <div className="cover-title-text" title={title}>
          {title}
        </div>
        <div className="cover-author-text" title={author}>
          {author}
        </div>
      </div>
    </div>
  );
};
