import { useId } from 'react';
import { ArrowRight } from 'lucide-react';

export function Architecture({ project, onSource }) {
  const marker = useId().replaceAll(':', '');
  const diagram = project.architecture;
  if (!diagram)
    return (
      <section className="fw-main-section">
        <h2>Architecture</h2>
        <p className="fw-muted">
          A visual architecture has not been documented for this project yet.
        </p>
      </section>
    );
  const positions = Object.fromEntries(
    diagram.nodes.map((node) => [
      node.id,
      { x: 20 + node.col * 245, y: 30 + node.row * 155 },
    ])
  );
  const height = 145 + Math.max(...diagram.nodes.map((node) => node.row)) * 155;
  const label = (id) => diagram.nodes.find((node) => node.id === id)?.label;
  return (
    <section className="fw-main-section fw-architecture">
      <h2>{diagram.title}</h2>
      <p className="fw-lead">{diagram.caption}</p>
      <figure>
        <figcaption>
          Component and data flow{' '}
          <span>Scroll horizontally on smaller screens.</span>
        </figcaption>
        <div
          className="fw-diagram-scroll"
          // Keyboard users must be able to scroll the wide diagram region.
          // eslint-disable-next-line jsx-a11y/no-noninteractive-tabindex
          tabIndex={0}
          role="region"
          aria-label={`${project.name} architecture diagram, horizontally scrollable`}
        >
          <svg
            viewBox={`0 0 740 ${height}`}
            role="img"
            aria-labelledby={`${marker}-title ${marker}-description`}
          >
            <title id={`${marker}-title`}>{project.name} architecture</title>
            <desc id={`${marker}-description`}>
              {diagram.edges
                .map(
                  (edge) =>
                    `${label(edge.source)} to ${label(edge.target)}: ${edge.label}.`
                )
                .join(' ')}
            </desc>
            <defs>
              <marker
                id={marker}
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#567d70" />
              </marker>
            </defs>
            {diagram.edges.map((edge) => {
              const a = positions[edge.source];
              const b = positions[edge.target];
              const vertical = a.y !== b.y;
              const x1 = a.x + (vertical ? 105 : a.x < b.x ? 210 : 0);
              const y1 = a.y + (vertical ? (a.y < b.y ? 74 : 0) : 37);
              const x2 = b.x + (vertical ? 105 : a.x < b.x ? 0 : 210);
              const y2 = b.y + (vertical ? (a.y < b.y ? 0 : 74) : 37);
              return (
                <path
                  key={`${edge.source}-${edge.target}`}
                  d={`M ${x1} ${y1} C ${vertical ? x1 : (x1 + x2) / 2} ${vertical ? (y1 + y2) / 2 : y1}, ${vertical ? x2 : (x1 + x2) / 2} ${vertical ? (y1 + y2) / 2 : y2}, ${x2} ${y2}`}
                  fill="none"
                  stroke="#567d70"
                  strokeWidth="2"
                  markerEnd={`url(#${marker})`}
                />
              );
            })}
            {diagram.nodes.map((node, i) => (
              <g
                key={node.id}
                transform={`translate(${positions[node.id].x},${positions[node.id].y})`}
              >
                <rect
                  width="210"
                  height="74"
                  rx="10"
                  fill={i === 0 ? '#173c35' : '#fff'}
                  stroke="#bdcec5"
                />
                <text
                  x="16"
                  y="26"
                  fontSize="11"
                  fill={i === 0 ? '#d5ee85' : '#576b64'}
                >
                  {String(i + 1).padStart(2, '0')}
                </text>
                <text
                  x="16"
                  y="51"
                  fontSize="14"
                  fontWeight="700"
                  fill={i === 0 ? '#fff' : '#18362f'}
                >
                  {node.label}
                </text>
              </g>
            ))}
          </svg>
        </div>
      </figure>
      <h3 className="fw-section-label">How the pieces connect</h3>
      <ol className="fw-flow-steps">
        {diagram.edges.map((edge) => (
          <li key={`${edge.source}-${edge.target}`}>
            <strong>
              {label(edge.source)} <ArrowRight size={14} aria-hidden="true" />{' '}
              {label(edge.target)}
            </strong>
            <span>{edge.label}</span>
          </li>
        ))}
      </ol>
      <details className="fw-component-notes">
        <summary>Component responsibilities</summary>
        <dl>
          {diagram.nodes.map((node) => (
            <div key={node.id}>
              <dt>{node.label}</dt>
              <dd>{node.detail}</dd>
            </div>
          ))}
        </dl>
      </details>
      {!!project.documents.length && (
        <button
          className="fw-text-button"
          onClick={() =>
            onSource(`${project.documents[0].id}#architecture-flow`)
          }
        >
          Read the architecture source <ArrowRight size={15} />
        </button>
      )}
    </section>
  );
}
