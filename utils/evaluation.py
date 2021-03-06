import torch


# src: https://github.com/DTrimarchi10/confusion_matrix
def draw_confusion_matrix(cf,
                          group_names=None,
                          categories='auto',
                          count=True,
                          percent=True,
                          cbar=True,
                          xyticks=True,
                          xyplotlabels=True,
                          sum_stats=True,
                          omit_diagonal=False,
                          figsize=None,
                          cmap='Blues',
                          title=None):
    """
    This function will make a pretty plot of an sklearn Confusion Matrix cm using a Seaborn heatmap visualization.
    Arguments
    ---------
    cf:            confusion matrix to be passed in
    group_names:   List of strings that represent the labels row by row to be shown in each square.
    categories:    List of strings containing the categories to be displayed on the x,y axis. Default is 'auto'
    count:         If True, show the raw number in the confusion matrix. Default is True.
    percent:       If True, show the proportions for each category. Default is True.
    cbar:          If True, show the color bar. The cbar values are based off the values in the confusion matrix.
                   Default is True.
    xyticks:       If True, show x and y ticks. Default is True.
    xyplotlabels:  If True, show 'True Label' and 'Predicted Label' on the figure. Default is True.
    sum_stats:     If True, display summary statistics below the figure. Default is True.
    omit_diagonal: If True, omit diagonal elements of confusion matrix.
    figsize:       Tuple representing the figure size. Default will be the matplotlib rcParams value.
    cmap:          Colormap of the values displayed from matplotlib.pyplot.cm. Default is 'Blues'
                   See http://matplotlib.org/examples/color/colormaps_reference.html
    title:         Title for the heatmap. Default is None.
    """

    import matplotlib.pyplot as plt
    import seaborn as sns
    import numpy as np

    # CODE TO GENERATE SUMMARY STATISTICS & TEXT FOR SUMMARY STATS
    if not omit_diagonal and sum_stats:
        #Accuracy is sum of diagonal divided by total observations
        accuracy  = np.trace(cf) / float(np.sum(cf))

        #if it is a binary confusion matrix, show some more stats
        if len(cf)==2:
            #Metrics for Binary Confusion Matrices
            precision = cf[1,1] / sum(cf[:,1])
            recall    = cf[1,1] / sum(cf[1,:])
            f1_score  = 2*precision*recall / (precision + recall)
            stats_text = "\n\nAccuracy={:0.3f}\nPrecision={:0.3f}\nRecall={:0.3f}\nF1 Score={:0.3f}".format(
                accuracy, precision, recall, f1_score)
        else:
            stats_text = "\n\nAccuracy={:0.3f}".format(accuracy)
    else:
        stats_text = ""

    if omit_diagonal:
        cf -= np.diagflat(np.diagonal(cf))

    # CODE TO GENERATE TEXT INSIDE EACH SQUARE
    blanks = ['' for _ in range(cf.size)]

    if group_names and len(group_names)==cf.size:
        group_labels = ["{}\n".format(value) for value in group_names]
    else:
        group_labels = blanks

    if count:
        group_counts = ["{0:0.0f}\n".format(value) for value in cf.flatten()]
    else:
        group_counts = blanks

    if percent:
        group_percentages = ["{0:.2%}".format(value) for value in cf.flatten()/np.sum(cf)]
    else:
        group_percentages = blanks

    box_labels = [f"{v1}{v2}{v3}".strip() for v1, v2, v3 in zip(group_labels,group_counts,group_percentages)]
    box_labels = np.asarray(box_labels).reshape(cf.shape[0],cf.shape[1])

    if omit_diagonal:
        box_labels[np.diag_indices_from(box_labels)] = ""

    # SET FIGURE PARAMETERS ACCORDING TO OTHER ARGUMENTS
    if figsize is None:
        #Get default figure size if not set
        figsize = plt.rcParams.get('figure.figsize')

    if not xyticks:
        #Do not show categories if xyticks is False
        categories=False

    # MAKE THE HEATMAP VISUALIZATION
    plt.figure(figsize=figsize)
    sns.heatmap(cf,annot=box_labels,fmt="",cmap=cmap,cbar=cbar,xticklabels=categories,yticklabels=categories)

    if xyplotlabels:
        plt.ylabel('True label')
        plt.xlabel('Predicted label' + stats_text)
    else:
        plt.xlabel(stats_text)

    if title:
        plt.title(title)


@torch.no_grad()
def all_together(model, dataset, device=None, verbose=True):
    import torch
    import torch.nn.functional as F
    import models.functional as f
    from sklearn.metrics import confusion_matrix
    try:
        from tqdm.notebook import tqdm
        iterator = tqdm(dataset, total=len(dataset), leave=False)
    except (ImportError, TypeError, ValueError):
        iterator = iter(dataset)
    device = device or torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
    model.eval().to(device)
    logits, targets = [], []
    total = correct = 0
    bce = dice = iou = 0.
    for x, true in iterator:
        if x.ndim == 4:
            size = x.size(0)
        elif x.ndim == 3:  # convert as batch
            x = x.unsqueeze(0)
            true = true.unsqueeze(0)
            size = 1
        else:
            raise TypeError("Invalid Input Dim")
        x = x.to(device).float()
        true = true.clamp(0., 1.).to(device).float()
        pred = model(x)
        pred = pred["out"]
        # print out the result of heart
        bce += F.binary_cross_entropy(pred.softmax(dim=-3), true, reduction='mean').item() * size
        true_argmax = true.argmax(dim=-3).long()
        pred_argmax = pred.argmax(dim=-3).long()
        logits.append(pred_argmax.view(-1))
        targets.append(true_argmax.view(-1))
        correct += torch.eq(pred_argmax, true_argmax).float().mean().item() * size
        pred = f.one_hot_nd(pred_argmax, pred.size(dim=-3), nd=2).to(pred.dtype)
        mul, add = pred * true, pred + true
        dice += f._dice_loss(mul, add, nd=2, reduction='mean').item() * size
        iou += f._iou_loss(mul, add, nd=2, reduction='mean').item() * size
        total += size
    logits = torch.cat(logits).cpu().numpy()
    targets = torch.cat(targets).cpu().numpy()
    cm = confusion_matrix(targets, logits, labels=range(6))
    correct /= total
    bce /= total
    dice /= total
    iou /= total
    if verbose:
        print(
            "Model Architecture:      {}\n"
            "Binary Cross Entropy:    {:7.5f}\n"
            "Dice-Coefficient:        {:7.5f}\n"
            "Intersection over Union: {:7.5f}\n"
            "Pixel-Wise Accuracy:     {:7.4f}%"
            .format(type(model).__name__, bce, 1 - dice, 1 - iou, correct * 100)
        )
    return bce, dice, iou, correct, cm


__all__ = ['draw_confusion_matrix', 'all_together']
