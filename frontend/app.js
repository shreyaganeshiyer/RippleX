// ============================================================
// RIPPLEX FRONTEND
// ============================================================

const noticeInput = document.getElementById("notice");
const analyzeButton = document.getElementById("analyzeButton");

const results = document.getElementById("results");
const reviewState = document.getElementById("reviewState");

const errorMessage = document.getElementById("errorMessage");


// ============================================================
// HELPERS
// ============================================================

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatNumber(value) {
    return Number(value || 0).toLocaleString("en-IN");
}


function formatCurrency(value) {
    return Number(value || 0).toLocaleString(
        "en-IN",
        {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 0
        }
    );
}


function showError(message) {
    errorMessage.textContent = message;
    errorMessage.classList.remove("hidden");
}


function hideError() {
    errorMessage.textContent = "";
    errorMessage.classList.add("hidden");
}


function setLoading(loading) {

    analyzeButton.disabled = loading;

    if (loading) {
        analyzeButton.innerHTML = `
            <span>◌</span>
            Analyzing...
        `;
    } else {
        analyzeButton.innerHTML = `
            <span>⚡</span>
            Analyze Disruption
        `;
    }
}


// ============================================================
// CLOCK
// ============================================================

function updateClock() {

    const now = new Date();

    const date = now.toLocaleDateString(
        "en-IN",
        {
            day: "2-digit",
            month: "short",
            year: "numeric"
        }
    );

    const time = now.toLocaleTimeString(
        "en-IN",
        {
            hour: "2-digit",
            minute: "2-digit",
            hour12: false
        }
    );

    document.getElementById(
        "currentTime"
    ).textContent = `${date} · ${time} IST`;
}

updateClock();

setInterval(
    updateClock,
    1000
);


// ============================================================
// BACKEND HEALTH
// ============================================================

async function checkBackend() {

    const status = document.getElementById(
        "backendStatus"
    );

    const statusText = document.getElementById(
        "statusText"
    );

    try {

        const response = await fetch(
            "/api/health"
        );

        if (!response.ok) {
            throw new Error(
                "Backend returned an error."
            );
        }

        status.className =
            "status-pill online";

        statusText.textContent =
            "Backend Online";

    } catch (error) {

        status.className =
            "status-pill offline";

        statusText.textContent =
            "Backend Unavailable";
    }
}

checkBackend();


// ============================================================
// EVENT RENDERING
// ============================================================

function renderEvent(event) {

    const container = document.getElementById(
        "eventContent"
    );

    const products = (
        event.affected_products || []
    ).join(", ") || "Not identified";

    container.innerHTML = `

        <div class="event-item">

            <div class="event-label">
                Event Type
            </div>

            <div class="event-value">
                ${escapeHtml(
                    event.event_type || "Unknown"
                )}
            </div>

        </div>


        <div class="event-item">

            <div class="event-label">
                Supplier
            </div>

            <div class="event-value">
                ${escapeHtml(
                    event.supplier_name || "Not identified"
                )}
            </div>

        </div>


        <div class="event-item">

            <div class="event-label">
                Location
            </div>

            <div class="event-value">
                ${escapeHtml(
                    event.location || "Not identified"
                )}
            </div>

        </div>


        <div class="event-item">

            <div class="event-label">
                Expected Delay
            </div>

            <div class="event-value">
                ${
                    event.delay_days !== null &&
                    event.delay_days !== undefined
                        ? `${escapeHtml(event.delay_days)} days`
                        : "Not specified"
                }
            </div>

        </div>


        <div class="event-item event-summary">

            <div class="event-label">
                Extracted Summary
            </div>

            <div class="event-value">
                ${escapeHtml(
                    event.summary || "No summary available."
                )}
            </div>

        </div>


        <div class="event-item event-summary">

            <div class="event-label">
                Affected Products
            </div>

            <div class="event-value">
                ${escapeHtml(products)}
            </div>

        </div>
    `;
}


// ============================================================
// IMPACT
// ============================================================

function renderImpact(impact) {

    document.getElementById(
        "ordersAtRisk"
    ).textContent = formatNumber(
        impact.total_orders_at_risk
    );

    document.getElementById(
        "unitsAtRisk"
    ).textContent = formatNumber(
        impact.total_units_at_risk
    );

    document.getElementById(
        "valueAtRisk"
    ).textContent = formatCurrency(
        impact.total_order_value_at_risk
    );

    document.getElementById(
        "shipmentsAffected"
    ).textContent = formatNumber(
        (impact.affected_shipments || []).length
    );

    document.getElementById(
        "impactSummary"
    ).textContent =
        impact.summary ||
        "No impact summary available.";
}


// ============================================================
// IMPACT CHAIN
// ============================================================

function renderImpactChain(
    event,
    impact
) {

    const shipments =
        impact.affected_shipments || [];

    const orders =
        impact.affected_orders || [];

    const products =
        impact.affected_products || [];

    const supplierNames = [
        ...new Set(
            shipments.map(
                shipment =>
                    shipment.supplier_name
            )
        )
    ];

    const shipmentIds = [
        ...new Set(
            shipments.map(
                shipment =>
                    shipment.shipment_id
            )
        )
    ];

    const productNames = [
        ...new Set(
            shipments.map(
                shipment =>
                    shipment.product_name
            )
        )
    ];

    const warehouseNames = [
        ...new Set(
            shipments.map(
                shipment =>
                    shipment.warehouse_name
            )
        )
    ];

    const customers = [
        ...new Set(
            orders.map(
                order =>
                    order.customer_name
            )
        )
    ];

    document.getElementById(
        "chainSupplier"
    ).textContent =
        supplierNames.join(", ") ||
        event.supplier_name ||
        "—";

    document.getElementById(
        "chainShipment"
    ).textContent =
        shipmentIds.length
            ? `${shipmentIds.length} affected`
            : "—";

    document.getElementById(
        "chainProduct"
    ).textContent =
        productNames.join(", ") ||
        products.map(
            product => product.product_name
        ).join(", ") ||
        "—";

    document.getElementById(
        "chainWarehouse"
    ).textContent =
        warehouseNames.join(", ") ||
        "—";

    document.getElementById(
        "chainOrders"
    ).textContent =
        `${orders.length} affected`;

    document.getElementById(
        "chainCustomers"
    ).textContent =
        `${customers.length} customers`;
}


// ============================================================
// ORDERS
// ============================================================
function renderOrders(orders) {

    const tbody = document.getElementById(
        "ordersTable"
    );

    if (!orders.length) {

        tbody.innerHTML = `
            <tr>
                <td colspan="9">
                    No affected orders.
                </td>
            </tr>
        `;

        return;
    }

    tbody.innerHTML = orders.map(
        order => `

            <tr>

                <td class="order-id">
                    ${escapeHtml(order.order_id)}
                </td>

                <td>
                    ${escapeHtml(order.customer_name)}
                </td>

                <td>
                    ${escapeHtml(order.product_name)}
                </td>

                <td>
                    ${formatNumber(order.quantity)}
                </td>

                <td class="shortage">
                    ${formatNumber(
                        order.shortage_quantity
                    )}
                </td>

                <td>
                    <span class="priority ${escapeHtml(
                        order.priority
                    )}">
                        ${escapeHtml(
                            order.priority
                        )}
                    </span>
                </td>

                <td>
                    ${formatNumber(
                        order.urgency_score
                    )}
                </td>

                <td>
                    ${
                        order.revised_delivery_date
                            ? `<strong>${escapeHtml(
                                order.revised_delivery_date
                            )}</strong>`
                            : "—"
                    }
                </td>

                <td>
                    ${formatCurrency(
                        order.order_value_at_risk
                    )}
                </td>

            </tr>
        `
    ).join("");
}


// ============================================================
// RESPONSE OPTIONS
// ============================================================

function renderResponseOptions(
    options,
    recommendation
) {

    const container = document.getElementById(
        "responseOptions"
    );

    if (!options.length) {

        container.innerHTML = `
            <div class="option-card">
                No response options available.
            </div>
        `;

        return;
    }

    const recommendedType =
        recommendation?.recommended_option_type;

    container.innerHTML = options.map(
        option => {

            const isRecommended =
                option.option_type ===
                recommendedType;

            return `

                <div class="option-card ${
                    isRecommended
                        ? "recommended"
                        : ""
                }">

                    <div class="option-header">

                        <div>

                            <div class="option-title">
                                ${escapeHtml(
                                    option.title
                                )}
                            </div>

                            <div class="option-type">
                                ${escapeHtml(
                                    option.option_type
                                )}
                            </div>

                        </div>

                        ${
                            isRecommended
                                ? `
                                    <div class="option-type"
                                         style="color:#40d99b">
                                        RECOMMENDED
                                    </div>
                                  `
                                : ""
                        }

                    </div>


                    <div class="option-description">
                        ${escapeHtml(
                            option.description
                        )}
                    </div>


                    <div class="option-metrics">

                        <div class="option-metric">

                            <div class="option-metric-label">
                                Units
                            </div>

                            <div class="option-metric-value">
                                ${formatNumber(
                                    option.units_recovered
                                )}
                            </div>

                        </div>


                        <div class="option-metric">

                            <div class="option-metric-label">
                                Orders
                            </div>

                            <div class="option-metric-value">
                                ${formatNumber(
                                    option.orders_helped
                                )}
                            </div>

                        </div>


                        <div class="option-metric">

                            <div class="option-metric-label">
                                Cost
                            </div>

                            <div class="option-metric-value">
                                ${formatCurrency(
                                    option.estimated_cost
                                )}
                            </div>

                        </div>

                    </div>


                    <div class="option-tradeoff">

                        <strong>
                            Trade-off:
                        </strong>

                        ${escapeHtml(
                            option.tradeoff
                        )}

                    </div>


                    <div class="feasibility ${
                        option.feasible
                            ? "feasible"
                            : "infeasible"
                    }">

                        ${
                            option.feasible
                                ? "✓ FEASIBLE"
                                : "✕ NOT FEASIBLE"
                        }

                    </div>

                </div>
            `;
        }
    ).join("");
}


// ============================================================
// RECOMMENDATION
// ============================================================

function renderRecommendation(
    recommendation
) {
     window.ripplexLastRecommendation =

        recommendation || null;

    const panel = document.getElementById(
        "recommendationPanel"
    );

    if (!recommendation) {

        panel.classList.add("hidden");

        return;
    }

    panel.classList.remove("hidden");

    document.getElementById(
        "recommendationTitle"
    ).textContent =
        recommendation.title ||
        "Human review required";

    document.getElementById(
        "recommendationReasoning"
    ).textContent =
        recommendation.reasoning ||
        "";

    document.getElementById(
        "recommendationMetrics"
    ).innerHTML = `

        <div class="recommendation-metric">
            ${escapeHtml(
                recommendation.recommended_option_type
            )}
        </div>

        <div class="recommendation-metric">
            ${formatNumber(
                recommendation.expected_units_recovered
            )} units
        </div>

        <div class="recommendation-metric">
            ${formatNumber(
                recommendation.orders_protected
            )} orders
        </div>

        <div class="recommendation-metric">
            ${formatCurrency(
                recommendation.estimated_cost
            )}
        </div>

        <div class="recommendation-metric">
            Confidence:
            ${Math.round(
                Number(
                    recommendation.confidence || 0
                ) * 100
            )}%
        </div>
    `;
}


// ============================================================
// EVIDENCE
// ============================================================

function renderEvidence(impact, options) {
    const container = document.getElementById("evidenceList");

    const groups = {
        "Supply": [],
        "Inventory": [],
        "Customer Impact": [],
        "Response": [],
        "Recommendation": [],
        "Impact": []
    };

    // ------------------------------------------------------------
    // Collect evidence
    // ------------------------------------------------------------

    for (const item of impact?.evidence || []) {
        groups["Impact"].push(item);
    }

    for (const shipment of impact?.affected_shipments || []) {
        for (const item of shipment.evidence || []) {
            groups["Supply"].push(item);
        }
    }

    for (const inventory of impact?.inventory_impacts || []) {
        for (const item of inventory.evidence || []) {
            groups["Inventory"].push(item);
        }
    }

    for (const order of impact?.affected_orders || []) {
        for (const item of order.evidence || []) {
            groups["Customer Impact"].push(item);
        }
    }

    for (const option of options || []) {
        for (const item of option.evidence || []) {
            groups["Response"].push(item);
        }
    }

    const recommendation = window.ripplexLastRecommendation;

    for (const item of recommendation?.evidence || []) {
        groups["Recommendation"].push(item);
    }

    // ------------------------------------------------------------
    // Deduplicate
    // ------------------------------------------------------------

    for (const category of Object.keys(groups)) {
        const seen = new Set();

        groups[category] = groups[category].filter(item => {
            const key = [
                item.source_type,
                item.source_id,
                item.description
            ].join("|");

            if (seen.has(key)) {
                return false;
            }

            seen.add(key);
            return true;
        });
    }

    // ------------------------------------------------------------
    // Metadata
    // ------------------------------------------------------------

    const categoryMeta = {
        "Supply": {
            icon: "↗",
            label: "Supply disruption",
            description: "Affected shipments and incoming supply"
        },

        "Inventory": {
            icon: "▣",
            label: "Inventory impact",
            description: "Warehouse stock supporting the assessment"
        },

        "Customer Impact": {
            icon: "◎",
            label: "Customer impact",
            description: "Orders with quantified exposure"
        },

        "Response": {
            icon: "◆",
            label: "Response analysis",
            description: "Evidence behind available response options"
        },

        "Recommendation": {
            icon: "★",
            label: "Recommendation",
            description: "Evidence supporting the selected response"
        },

        "Impact": {
            icon: "⌁",
            label: "Impact calculation",
            description: "Deterministic calculations from supply-chain data"
        }
    };

    // ------------------------------------------------------------
    // Choose only the most useful evidence
    // ------------------------------------------------------------

    function selectUsefulEvidence(category, items) {
        if (!items.length) {
            return [];
        }

        // Keep the most important records visible.
        // The rest remain represented by the "+ X more" indicator.
        if (category === "Supply") {
            return items.slice(0, 3);
        }

        if (category === "Inventory") {
            return items.slice(0, 2);
        }

        if (category === "Customer Impact") {
            return items.slice(0, 3);
        }

        if (category === "Response") {
            return items.slice(0, 4);
        }

        if (category === "Recommendation") {
            return items.slice(0, 2);
        }

        if (category === "Impact") {
            return items.slice(0, 3);
        }

        return items.slice(0, 2);
    }

    // ------------------------------------------------------------
    // Render
    // ------------------------------------------------------------

    const visibleGroups = Object.entries(groups)
        .filter(([, items]) => items.length > 0);

    if (!visibleGroups.length) {
        container.innerHTML = `
            <div class="evidence-empty">
                <div class="evidence-empty-icon">✓</div>
                <div>
                    <strong>No evidence records returned</strong>
                    <span>
                        The analysis did not produce traceable source records.
                    </span>
                </div>
            </div>
        `;
        return;
    }

    container.innerHTML = visibleGroups
        .map(([category, items]) => {
            const meta = categoryMeta[category];
            const visibleItems = selectUsefulEvidence(category, items);
            const remaining = items.length - visibleItems.length;

            return `
                <section class="evidence-group">

                    <div class="evidence-group-header">

                        <div class="evidence-group-title">

                            <div class="evidence-group-icon">
                                ${meta.icon}
                            </div>

                            <div>
                                <div class="evidence-group-name">
                                    ${escapeHtml(meta.label)}
                                </div>

                                <div class="evidence-group-description">
                                    ${escapeHtml(meta.description)}
                                </div>
                            </div>

                        </div>

                        <div class="evidence-count">
                            ${items.length}
                            ${items.length === 1 ? "source" : "sources"}
                        </div>

                    </div>

                    <div class="evidence-group-items">

                        ${visibleItems.map(item => `
                            <article class="evidence-card">

                                <div class="evidence-card-top">

                                    <span class="evidence-source-type">
                                        ${escapeHtml(
                                            String(
                                                item.source_type || "SOURCE"
                                            ).toUpperCase()
                                        )}
                                    </span>

                                    <span class="evidence-source-id">
                                        ${escapeHtml(
                                            item.source_id || "—"
                                        )}
                                    </span>

                                </div>

                                <div class="evidence-card-description">
                                    ${escapeHtml(
                                        item.description ||
                                        "No description available."
                                    )}
                                </div>

                            </article>
                        `).join("")}

                        ${
                            remaining > 0
                                ? `
                                    <div class="evidence-more">
                                        + ${remaining} more
                                        ${remaining === 1 ? "source" : "sources"}
                                        available in the analysis
                                    </div>
                                  `
                                : ""
                        }

                    </div>

                </section>
            `;
        })
        .join("");
}


// ============================================================
// HUMAN REVIEW
// ============================================================

function renderHumanReview(
    resolution,
    impact
) {

    const panel = document.getElementById(
        "reviewState"
    );

    if (impact.has_impact) {

        panel.classList.add("hidden");

        return;
    }

    panel.classList.remove("hidden");

    document.getElementById(
        "reviewMessage"
    ).textContent =
        impact.summary ||
        "RippleX could not safely establish business impact.";

    const unresolved =
        resolution?.unresolved_entities || [];

    const details =
        document.getElementById(
            "resolutionDetails"
        );

    if (!unresolved.length) {

        details.innerHTML = "";

        return;
    }

    details.innerHTML = unresolved.map(
        entity => `

            <div class="evidence-item">

                <div class="evidence-type">
                    ${escapeHtml(
                        entity.entity_type
                    )}
                </div>

                <div class="evidence-id">
                    ${escapeHtml(
                        entity.input_value
                    )}
                </div>

                <div class="evidence-description">
                    ${escapeHtml(
                        entity.reason
                    )}
                </div>

            </div>
        `
    ).join("");
}


// ============================================================
// MAIN ANALYSIS
// ============================================================

async function analyzeDisruption() {

    hideError();

    const notice =
        noticeInput.value.trim();

    if (!notice) {

        showError(
            "Please enter a disruption notice."
        );

        noticeInput.focus();

        return;
    }

    setLoading(true);

    results.classList.add("hidden");
    reviewState.classList.add("hidden");

    try {

        const response = await fetch(
            "/api/analyze",
            {
                method: "POST",

                headers: {
                    "Content-Type":
                        "application/json"
                },

                body: JSON.stringify({
                    notice: notice
                })
            }
        );

        const data =
            await response.json();

        if (!response.ok) {

            const message =
                data?.detail?.message ||
                data?.detail ||
                "Analysis failed.";

            throw new Error(
                message
            );
        }


        // ----------------------------------------------------
        // Render event
        // ----------------------------------------------------

        renderEvent(
            data.event || {}
        );


        // ----------------------------------------------------
        // Render impact
        // ----------------------------------------------------

        const impact =
            data.impact || {};

        renderImpact(
            impact
        );


        // ----------------------------------------------------
        // Render chain
        // ----------------------------------------------------

        renderImpactChain(
            data.event || {},
            impact
        );


        // ----------------------------------------------------
        // Render orders
        // ----------------------------------------------------

        renderOrders(
            impact.affected_orders || []
        );


        // ----------------------------------------------------
        // Render responses
        // ----------------------------------------------------

        renderResponseOptions(
            data.response_options || [],
            data.recommendation
        );


        // ----------------------------------------------------
        // Render recommendation
        // ----------------------------------------------------

        renderRecommendation(
            data.recommendation
        );


        // ----------------------------------------------------
        // Render evidence
        // ----------------------------------------------------

        renderEvidence(
            impact,
            data.response_options || []
        );


        // ----------------------------------------------------
        // Human review / no-impact state
        // ----------------------------------------------------

        renderHumanReview(
            data.resolution,
            impact
        );


        // ----------------------------------------------------
        // Show appropriate UI
        // ----------------------------------------------------

        results.classList.remove(
            "hidden"
        );

    } catch (error) {

        console.error(
            "RippleX analysis error:",
            error
        );

        showError(
            error.message ||
            "Unable to analyze disruption."
        );

    } finally {

        setLoading(false);
    }
}


// ============================================================
// BUTTON
// ============================================================

analyzeButton.addEventListener(
    "click",
    analyzeDisruption
);


// ============================================================
// CTRL/CMD + ENTER
// ============================================================

noticeInput.addEventListener(
    "keydown",
    event => {

        if (
            (event.ctrlKey || event.metaKey) &&
            event.key === "Enter"
        ) {
            analyzeDisruption();
        }

    }
);