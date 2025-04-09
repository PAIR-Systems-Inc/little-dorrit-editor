// Load data from results.json
let leaderboardData = [];

// Create and configure the leaderboard table
const leaderboardTable = new Tabulator("#leaderboard-table", {
    data: leaderboardData,
    layout: "fitColumns",
    headerSort: true,
    index: "modelId", // Use model ID as the primary key
    initialSort: [{ column: "f1Score", dir: "desc" }], // Sort by F1 score descending
    columns: [
        {
            title: "Rank",
            field: "rank",
            sorter: "number",
            width: 50,
            headerSort: false,
            headerHozAlign: "center",
            hozAlign: "center",
        },
        {
            title: "Model",
            field: "model",
            widthGrow: 3,
            formatter: function(cell) {
                const value = cell.getValue();
                const row = cell.getRow().getData();
                let medalClass = "";
                let medalText = "";

                if (row.rank === 1) {
                    medalClass = "gold";
                    medalText = "1";
                } else if (row.rank === 2) {
                    medalClass = "silver";
                    medalText = "2";
                } else if (row.rank === 3) {
                    medalClass = "bronze";
                    medalText = "3";
                }

                const shots = row.shots || 2;
                const modelWithShots = `${value} (${shots}-shot)`;

                if (medalClass) {
                    return `<span class="medal ${medalClass}">${medalText}</span>${modelWithShots}`;
                }
                return modelWithShots;
            }
        },
        {
            title: "F1",
            field: "f1Score",
            sorter: "number",
            headerHozAlign: "right",
            hozAlign: "right",
            width: 80,
            formatter: function(cell) {
                return cell.getValue().toFixed(4);
            }
        },
        {
            title: "95% CI",
            field: "confidenceInterval",
            headerHozAlign: "right",
            hozAlign: "right",
            width: 100,
            formatter: function(cell) {
                const value = cell.getValue();
                if (value === "calculating...") {
                    return "<span class='loading-indicator'>calculating...</span>";
                }
                return value || "pending...";
            }
        },
        {
            title: "Prec.",
            field: "precision",
            sorter: "number",
            headerHozAlign: "right",
            hozAlign: "right",
            width: 80,
            formatter: function(cell) {
                return cell.getValue().toFixed(4);
            }
        },
        {
            title: "Recall",
            field: "recall",
            sorter: "number",
            headerHozAlign: "right",
            hozAlign: "right",
            width: 80,
            formatter: function(cell) {
                return cell.getValue().toFixed(4);
            }
        },
        {
            title: "Date",
            field: "date",
            sorter: "date",
            headerHozAlign: "center",
            hozAlign: "center",
            width: 100
        }
    ]
});

// Calculate F-beta score (F1 when beta=1)
function fBetaScore(precision, recall, beta = 1) {
    if (precision === 0 && recall === 0) return 0;

    const betaSquared = beta * beta;
    return (1 + betaSquared) * (precision * recall) /
           (betaSquared * precision + recall);
}

// Function to load JSON data from results.json and process it
async function loadResults() {
    try {
        const response = await fetch('results.json');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const rawData = await response.json();

        // Process the raw data to calculate metrics
        return processModelResults(rawData);
    } catch (error) {
        console.error('Error loading results:', error);
        return [];
    }
}

// Process model results and compute metrics
function processModelResults(data) {
    // First, process each model to calculate metrics
    const processedModels = data.map(model => {
        const fileResults = model.file_results || [];

        // Collect all edit matches from all files
        const allEditMatches = [];
        fileResults.forEach(fileResult => {
            // Handle both the new format (details is a list of EditMatch objects)
            // and the older format (details.edit_matches)
            const details = fileResult.details;
            if (Array.isArray(details)) {
                allEditMatches.push(...details);
            } else if (details && details.edit_matches) {
                allEditMatches.push(...details.edit_matches);
            }
        });

        // If no edit matches, return original model with placeholder metrics
        if (allEditMatches.length === 0) {
            return {
                ...model,
                precision: 0,
                recall: 0,
                f1_score: 0,
                details: {
                    ...(model.details || {}),
                    correct_count: 0,
                    total_predicted: 0,
                    total_ground_truth: 0,
                    file_results: fileResults
                }
            };
        }

        // Calculate overall metrics
        let totalTp = 0;
        let totalFp = 0;
        let totalFn = 0;

        // Process each edit match
        allEditMatches.forEach(edit => {
            // Add TP/FP/FN values to totals
            totalTp += edit.tp || 0;
            totalFp += edit.fp || 0;
            totalFn += edit.fn || 0;
        });

        // Calculate global metrics
        const precision = totalTp / (totalTp + totalFp) || 0;
        const recall = totalTp / (totalTp + totalFn) || 0;
        const f1_score = fBetaScore(precision, recall, 1);

        // Count "correct" edits (tp >= 0.5)
        const correctCount = allEditMatches.filter(edit => (edit.tp || 0) >= 0.5).length;
        const totalGT = allEditMatches.filter(edit => edit.expected_edit_num !== undefined && edit.expected_edit_num !== null).length;
        const totalPred = allEditMatches.filter(edit => edit.observed_edit_num !== undefined && edit.observed_edit_num !== null).length;

        // Return processed model with computed metrics
        return {
            ...model,
            precision,
            recall,
            f1_score,
            details: {
                precision,
                recall,
                f1_score,
                correct_count: correctCount,
                total_ground_truth: totalGT,
                total_predicted: totalPred,
                file_results: fileResults
            }
        };
    });

    // Then sort by F1 score
    return processedModels.sort((a, b) => (b.f1_score || 0) - (a.f1_score || 0));
}

// Function to find a model in the results data
function findModel(results, modelName) {
    return results.find(model => model.model_name === modelName);
}

// Bootstrap confidence interval calculation
function groupByFileId(fileResults) {
    const groups = {};
    fileResults.forEach(result => {
        const fileId = result.file_id || result.id || "unknown";
        if (!groups[fileId]) {
            groups[fileId] = [];
        }
        groups[fileId].push(result);
    });
    return groups;
}

function sampleWithReplacement(array, size) {
    const result = [];
    for (let i = 0; i < size; i++) {
        const randomIndex = Math.floor(Math.random() * array.length);
        result.push(array[randomIndex]);
    }
    return result;
}

function getEditMatches(fileResult) {
    const details = fileResult.details;
    if (Array.isArray(details)) {
        return details;
    } else if (details && details.edit_matches) {
        return details.edit_matches;
    }
    return [];
}

// Compute a single bootstrap replicate
function computeOneBootstrapReplicate(model) {
    // Group file results by file_id
    const fileGroups = groupByFileId(model.file_results || []);

    // If no file groups, return null
    if (Object.keys(fileGroups).length === 0) {
        return null;
    }

    // Sample files with replacement
    const sampledFiles = sampleWithReplacement(Object.keys(fileGroups), Object.keys(fileGroups).length);

    // For each sampled file, randomly select one run if multiple exist
    let totalTp = 0, totalFp = 0, totalFn = 0;

    sampledFiles.forEach(fileId => {
        const runs = fileGroups[fileId];
        const selectedRun = runs[Math.floor(Math.random() * runs.length)];

        // Extract edit matches from the selected run
        const editMatches = getEditMatches(selectedRun);

        // Accumulate TP, FP, FN counts
        editMatches.forEach(edit => {
            totalTp += edit.tp || 0;
            totalFp += edit.fp || 0;
            totalFn += edit.fn || 0;
        });
    });

    // Calculate metrics only once using the aggregated counts
    const precision = totalTp / (totalTp + totalFp) || 0;
    const recall = totalTp / (totalTp + totalFn) || 0;
    const f1_score = fBetaScore(precision, recall, 1);

    return { precision, recall, f1_score };
}

// Calculate confidence intervals through bootstrap
async function calculateModelConfidenceIntervals(model, chunkSize = 10) {
    if (!model || !model.file_results || model.file_results.length === 0) {
        model.confidenceInterval = "N/A";
        return;
    }

    const totalReplicates = 1000;
    const bootstrapResults = [];
    model.confidenceInterval = "calculating...";

    for (let i = 0; i < totalReplicates; i += chunkSize) {
        // Allow UI to update between chunks
        await new Promise(resolve => setTimeout(resolve, 0));

        // Process a chunk of bootstrap replicates
        const chunkResults = [];
        for (let j = 0; j < chunkSize && i + j < totalReplicates; j++) {
            const result = computeOneBootstrapReplicate(model);
            if (result) {
                chunkResults.push(result);
            }
        }

        bootstrapResults.push(...chunkResults);

        // Update UI with partial results
        updateConfidenceIntervals(model, bootstrapResults);
    }
}

// Update confidence intervals in the UI
function updateConfidenceIntervals(model, bootstrapResults) {
    if (bootstrapResults.length > 0) {
        // Sort results for percentile calculation
        const sortedF1Scores = bootstrapResults.map(r => r.f1_score).sort((a, b) => a - b);

        // Calculate percentiles for 95% CI
        const lowerIdx = Math.floor(0.025 * sortedF1Scores.length);
        const upperIdx = Math.floor(0.975 * sortedF1Scores.length);

        const lowerBound = sortedF1Scores[lowerIdx];
        const upperBound = sortedF1Scores[upperIdx];

        // Format as +/-
        const pointEstimate = model.f1_score;
        const lowerDiff = (pointEstimate - lowerBound).toFixed(3);
        const upperDiff = (upperBound - pointEstimate).toFixed(3);

        model.confidenceInterval = `+${upperDiff}/-${lowerDiff}`;

        // Update the matching row in leaderboardData
        const modelId = model.model_id || model.model_name;
        const matchingRow = leaderboardData.find(row => row.modelId === modelId);
        if (matchingRow) {
            matchingRow.confidenceInterval = model.confidenceInterval;

            // Update just the cell for this model row
            leaderboardTable.updateData([{
                modelId: modelId,
                confidenceInterval: model.confidenceInterval
            }]);
        }
    }
}

// Function to prepare data for the detailed model performance table
async function prepareModelPerformanceData() {
    const results = await loadResults();
    const performanceData = [];

    for (const modelData of results) {
        if (!modelData) continue;

        // Get metrics from processed data
        const details = modelData.details || {};

        // Get all edit matches to calculate actual TP, FP, FN totals
        let totalModelTp = 0;
        let totalModelFp = 0;
        let totalModelFn = 0;
        
        // Collect all edit matches from all files
        const fileResultsData = details.file_results || modelData.file_results || [];
        fileResultsData.forEach(fileResult => {
            const fileDetails = fileResult.details;
            if (Array.isArray(fileDetails)) {
                fileDetails.forEach(edit => {
                    totalModelTp += edit.tp || 0;
                    totalModelFp += edit.fp || 0;
                    totalModelFn += edit.fn || 0;
                });
            }
        });
        
        // Add model summary row
        const modelRow = {
            id: modelData.model_name,
            model: modelData.model_name,
            precision: modelData.precision || 0,
            recall: modelData.recall || 0,
            f1_score: modelData.f1_score || 0,
            confidenceInterval: "pending...",
            true_positives: totalModelTp || 0,
            false_positives: totalModelFp || 0,
            false_negatives: totalModelFn || 0,
            _children: []
        };

        // Add file-specific rows as children
        const fileResults = details.file_results || modelData.file_results || [];
        for (const file of fileResults) {
            if (!file) continue;

            // Process each file's metrics - they might need to be computed
            let filePrecision = 0;
            let fileRecall = 0;
            let fileF1 = 0;
            let fileTp = 0;
            let fileFp = 0;
            let fileFn = 0;

            // Get metrics from the file if they exist
            if (file.precision !== undefined && file.recall !== undefined) {
                filePrecision = file.precision;
                fileRecall = file.recall;
                fileF1 = file.f1_score || fBetaScore(filePrecision, fileRecall);
            }

            // Get counts from file details
            const fileDetails = file.details || {};
            if (fileDetails.correct_count !== undefined) {
                fileTp = fileDetails.correct_count;
                fileFp = (fileDetails.total_predicted || 0) - fileTp;
                fileFn = (fileDetails.total_ground_truth || 0) - fileTp;
            } else if (Array.isArray(fileDetails)) {
                // New format - calculate from edit matches
                let totalTp = 0;
                let totalFp = 0;
                let totalFn = 0;

                fileDetails.forEach(edit => {
                    totalTp += edit.tp || 0;
                    totalFp += edit.fp || 0;
                    totalFn += edit.fn || 0;
                });

                filePrecision = totalTp / (totalTp + totalFp) || 0;
                fileRecall = totalTp / (totalTp + totalFn) || 0;
                fileF1 = fBetaScore(filePrecision, fileRecall);

                // Use actual values from the edits
                fileTp = totalTp;
                fileFp = totalFp;
                fileFn = totalFn;
            }

            // Add file row with its own children for runs
            const fileId = file.file_id || file.id || "unknown";
            const runId = file.run_id || "1";
            const runDate = file.date || "Unknown";
            
            // Format the date for display
            const formattedDate = runDate.includes("T") 
                ? new Date(runDate).toLocaleString() 
                : runDate;
                
            // Check if we already have this file in the children
            let fileRow = modelRow._children.find(child => child.id === `${modelData.model_name}-${fileId}`);
            
            if (!fileRow) {
                // Create a new file row if it doesn't exist
                fileRow = {
                    id: `${modelData.model_name}-${fileId}`,
                    model: `File ${fileId}`,
                    precision: filePrecision,
                    recall: fileRecall,
                    f1_score: fileF1,
                    true_positives: fileTp,
                    false_positives: fileFp,
                    false_negatives: fileFn,
                    _children: []  // This will contain individual runs
                };
                modelRow._children.push(fileRow);
            }
            
            // Add the current run as a child of the file row
            fileRow._children.push({
                id: `${modelData.model_name}-${fileId}-${runId}-${runDate}`,
                model: `Run ${formattedDate}`,
                precision: filePrecision,
                recall: fileRecall,
                f1_score: fileF1,
                true_positives: fileTp,
                false_positives: fileFp,
                false_negatives: fileFn
            });
            
            // Update file row metrics by summing all runs
            if (fileRow._children.length > 1) {
                // Sum up TP, FP, FN across all runs
                let totalFileTp = 0, totalFileFp = 0, totalFileFn = 0;
                
                fileRow._children.forEach(run => {
                    totalFileTp += run.true_positives || 0;
                    totalFileFp += run.false_positives || 0;
                    totalFileFn += run.false_negatives || 0;
                });
                
                // Recalculate metrics based on sums
                const filePrecision = totalFileTp / (totalFileTp + totalFileFp) || 0;
                const fileRecall = totalFileTp / (totalFileTp + totalFileFn) || 0;
                const fileF1 = fBetaScore(filePrecision, fileRecall);
                
                // Update file row with aggregated metrics
                fileRow.precision = filePrecision;
                fileRow.recall = fileRecall;
                fileRow.f1_score = fileF1;
                fileRow.true_positives = totalFileTp;
                fileRow.false_positives = totalFileFp;
                fileRow.false_negatives = totalFileFn;
                fileRow.model = `File ${fileId} (${fileRow._children.length} runs)`;
            }
        }

        performanceData.push(modelRow);
    }

    // Sort by F1 score
    return performanceData.sort((a, b) => (b.f1_score || 0) - (a.f1_score || 0));
}

// Function to create and configure the model performance table
async function createModelPerformanceTable() {
    const performanceData = await prepareModelPerformanceData();

    const performanceTable = new Tabulator("#model-performance-table", {
        data: performanceData,
        layout: "fitColumns",
        dataTree: true,
        dataTreeStartExpanded: false,
        dataTreeChildIndent: 15,
        dataTreeBranchElement: "<span class='tabulator-data-tree-branch'></span>",
        initialSort: [{ column: "f1_score", dir: "desc" }], // Sort by F1 score descending
        columns: [
            {
                title: "Model / File / Run",
                field: "model",
                widthGrow: 4,
                resizable: true
            },
            {
                title: "F1",
                field: "f1_score",
                width: 100,
                headerHozAlign: "right",
                hozAlign: "right",
                formatter: function(cell) {
                    const value = cell.getValue();
                    const formattedValue = value.toFixed(4);

                    let colorClass = "";
                    if (value >= 0.8) {
                        colorClass = "perfect-score";
                    } else if (value >= 0.5) {
                        colorClass = "good-score";
                    } else {
                        colorClass = "low-score";
                    }

                    return `<span><span class="performance-indicator ${colorClass}"></span>${formattedValue}</span>`;
                }
            },
            {
                title: "Precision",
                field: "precision",
                width: 100,
                headerHozAlign: "right",
                hozAlign: "right",
                formatter: function(cell) {
                    return cell.getValue().toFixed(4);
                }
            },
            {
                title: "Recall",
                field: "recall",
                width: 100,
                headerHozAlign: "right",
                hozAlign: "right",
                formatter: function(cell) {
                    return cell.getValue().toFixed(4);
                }
            },
            {
                title: "TP",
                field: "true_positives",
                width: 65,
                headerHozAlign: "right",
                hozAlign: "right",
                formatter: function(cell) {
                    return cell.getValue().toFixed(1);
                }
            },
            {
                title: "FP",
                field: "false_positives",
                width: 65,
                headerHozAlign: "right",
                hozAlign: "right",
                formatter: function(cell) {
                    return cell.getValue().toFixed(1);
                }
            },
            {
                title: "FN",
                field: "false_negatives",
                width: 65,
                headerHozAlign: "right",
                hozAlign: "right",
                formatter: function(cell) {
                    return cell.getValue().toFixed(1);
                }
            }
        ]
    });

    return performanceTable;
}

// Initialize everything
document.addEventListener("DOMContentLoaded", async function() {
    // Load data from results.json
    const results = await loadResults();
    // Note: results are already sorted by F1 score in processModelResults

    // Format the data for the leaderboard table
    if (results && results.length > 0) {
        leaderboardData = results.map((model, index) => ({
            rank: index + 1, // Assign rank based on sorted order
            modelId: model.model_id || model.model_name, // Use model_id as primary key
            model: model.model_name,
            shots: model.shots || 2,
            f1Score: model.f1_score,
            confidenceInterval: "pending...",
            precision: model.precision,
            recall: model.recall,
            date: model.date ? model.date.split('T')[0] : 'Unknown',
            // Store the original model data for bootstrap calculations
            originalModel: model
        }));

        // Update the leaderboard table with real data
        leaderboardTable.setData(leaderboardData);

        // Start calculating confidence intervals
        setTimeout(() => {
            leaderboardData.forEach(row => {
                calculateModelConfidenceIntervals(row.originalModel);
            });
        }, 1000); // Slight delay to let the table render first

        // Update metrics dynamically
        if (results.length > 0) {
            // Find top model (first in sorted results by F1 score)
            const topModel = results[0];
            document.getElementById("top-model").textContent = topModel.model_name;
            document.getElementById("top-model-name").textContent = "Highest F1 Score";

            // Find model with best F1 score
            const bestF1Index = results.reduce((maxIndex, model, currentIndex, arr) =>
                model.f1_score > arr[maxIndex].f1_score ? currentIndex : maxIndex, 0);
            const bestF1Model = results[bestF1Index];
            document.getElementById("best-f1-score").textContent = bestF1Model.f1_score.toFixed(4);
            document.getElementById("best-f1-model").textContent = bestF1Model.model_name;

            // Find model with best precision
            const bestPrecisionIndex = results.reduce((maxIndex, model, currentIndex, arr) =>
                model.precision > arr[maxIndex].precision ? currentIndex : maxIndex, 0);
            const bestPrecisionModel = results[bestPrecisionIndex];
            document.getElementById("best-precision").textContent = bestPrecisionModel.precision.toFixed(4);
            document.getElementById("best-precision-model").textContent = bestPrecisionModel.model_name;

            // Find model with best recall
            const bestRecallIndex = results.reduce((maxIndex, model, currentIndex, arr) =>
                model.recall > arr[maxIndex].recall ? currentIndex : maxIndex, 0);
            const bestRecallModel = results[bestRecallIndex];
            document.getElementById("best-recall").textContent = bestRecallModel.recall.toFixed(4);
            document.getElementById("best-recall-model").textContent = bestRecallModel.model_name;
        }
    }

    // Create detailed performance table
    createModelPerformanceTable();

    // Update the last updated date
    const lastDate = results.length > 0 ? new Date(results[0].date) : new Date();
    document.getElementById("last-updated").textContent = lastDate.toISOString().split('T')[0];
});